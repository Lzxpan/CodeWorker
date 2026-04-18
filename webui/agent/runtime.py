import difflib
import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from rag.index import impact_analysis, search_index


@dataclass
class PendingAction:
    id: str
    kind: str
    description: str
    payload: Dict[str, object]
    status: str = "pending"


PENDING_ACTIONS: Dict[str, PendingAction] = {}


def _safe_path(project_root: Path, relative_path: str) -> Path:
    target = (project_root / relative_path).resolve()
    root = project_root.resolve()
    if not str(target).startswith(str(root)):
        raise ValueError("Path escapes project root.")
    return target


def create_pending_action(kind: str, description: str, payload: Dict[str, object]) -> PendingAction:
    action = PendingAction(id=uuid.uuid4().hex, kind=kind, description=description, payload=payload)
    PENDING_ACTIONS[action.id] = action
    return action


def read_file(project_root: Path, relative_path: str, max_chars: int = 12000) -> Dict[str, object]:
    target = _safe_path(project_root, relative_path)
    content = target.read_text(encoding="utf-8", errors="replace")
    return {"path": relative_path, "content": content[:max_chars], "truncated": len(content) > max_chars}


def list_dir(project_root: Path, relative_path: str = "") -> Dict[str, object]:
    target = _safe_path(project_root, relative_path)
    items = []
    for child in sorted(target.iterdir(), key=lambda item: item.name.lower())[:200]:
        items.append({"name": child.name, "path": child.relative_to(project_root).as_posix(), "isDir": child.is_dir()})
    return {"path": relative_path, "items": items}


def search_project(project_root: Path, query: str, limit: int = 50) -> Dict[str, object]:
    matches = []
    lowered = query.lower()
    for path in project_root.rglob("*"):
        if not path.is_file() or len(matches) >= limit:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if lowered in content.lower():
            matches.append({"path": path.relative_to(project_root).as_posix()})
    return {"query": query, "matches": matches}


def preview_diff(project_root: Path, relative_path: str, content: str) -> Dict[str, object]:
    target = _safe_path(project_root, relative_path)
    before = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
    diff = "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            content.splitlines(),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
    )
    action = create_pending_action(
        "write_file",
        f"Write {relative_path}",
        {"path": relative_path, "content": content, "diff": diff},
    )
    return {"pendingAction": action.__dict__, "diff": diff}


def pending_command(command: str) -> Dict[str, object]:
    action = create_pending_action(
        "run_command",
        f"Run command: {command}",
        {"command": command},
    )
    return {"pendingAction": action.__dict__}


def write_audit(audit_dir: Optional[Path], payload: Dict[str, object]) -> None:
    if audit_dir is None:
        return
    audit_dir.mkdir(parents=True, exist_ok=True)
    with (audit_dir / "agent-actions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def confirm_action(project_root: Path, action_id: str, approved: bool, audit_dir: Optional[Path] = None) -> Dict[str, object]:
    action = PENDING_ACTIONS.get(action_id)
    if not action:
        raise ValueError("Pending action not found.")
    if not approved:
        action.status = "rejected"
        write_audit(audit_dir, {"id": action.id, "kind": action.kind, "status": action.status, "payload": action.payload})
        return {"id": action.id, "status": action.status}
    if action.kind == "write_file":
        target = _safe_path(project_root, str(action.payload.get("path", "")))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(action.payload.get("content", "")), encoding="utf-8")
        action.status = "applied"
        write_audit(audit_dir, {"id": action.id, "kind": action.kind, "status": action.status, "payload": {"path": action.payload.get("path")}})
        return {"id": action.id, "status": action.status, "path": str(target)}
    if action.kind == "run_command":
        completed = subprocess.run(
            str(action.payload.get("command", "")),
            cwd=str(project_root),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        action.status = "applied"
        write_audit(
            audit_dir,
            {
                "id": action.id,
                "kind": action.kind,
                "status": action.status,
                "payload": action.payload,
                "returncode": completed.returncode,
            },
        )
        return {
            "id": action.id,
            "status": action.status,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-6000:],
            "stderr": completed.stderr[-6000:],
        }
    raise ValueError(f"Unsupported action kind: {action.kind}")


def build_manifest(message: str, impacted: Dict[str, object]) -> Dict[str, object]:
    return {
        "summary": message,
        "items": [
            {
                "path": item.get("path"),
                "action": "INSPECT",
                "description": "Candidate impacted file for this request.",
                "reason": "Selected by dependency/import/signature impact analysis.",
                "dependencies": item.get("imports", []),
                "risk": "Requires human confirmation before write/execute actions.",
            }
            for item in impacted.get("impacted", [])[:12]
        ],
    }


def run_agent(project_root: Path, data_dir: Path, message: str) -> Dict[str, object]:
    rag_matches = search_index(project_root, data_dir, message, limit=6)
    impacted = impact_analysis(project_root, data_dir)
    manifest = build_manifest(message, impacted)
    events = [
        {"type": "observe", "message": "Loaded project index and current request."},
        {"type": "reasoning", "message": "Built a manifest before proposing any file changes."},
        {"type": "tool_call", "tool": "rag_search", "params": {"query": message}},
        {"type": "tool_result", "tool": "rag_search", "result": rag_matches},
        {"type": "finish", "message": "Agent v1 produced a safe manifest and requires explicit confirmation for write/execute actions."},
    ]
    return {"events": events, "manifest": manifest, "rag": rag_matches, "pendingActions": [action.__dict__ for action in PENDING_ACTIONS.values() if action.status == "pending"]}
