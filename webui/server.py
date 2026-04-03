import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
STATIC_DIR = Path(__file__).resolve().parent / "static"
CONFIG_DIR = ROOT_DIR / "config"
BOOTSTRAP_MANIFEST_PATH = CONFIG_DIR / "bootstrap.manifest.json"
LLM_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
MAX_SCAN_FILES = 800
MAX_TREE_ITEMS = 400
MAX_CONTEXT_FILES = 4
MAX_FILE_CHARS = 2200
MAX_TOTAL_CONTEXT = 8000
MAX_TREE_CONTEXT_ITEMS = 30
MAX_CHAT_HISTORY_ITEMS = 4
ATTACH_PROJECT_TIMEOUT_SECONDS = 180
START_SERVER_TIMEOUT_SECONDS = 120
IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "target", "out", ".idea", ".vscode", ".next", ".nuxt", ".cache", "coverage",
}
IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico", ".pdf", ".zip", ".7z", ".gz",
    ".tar", ".rar", ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".pyc", ".pyo", ".db",
    ".sqlite", ".mp3", ".mp4", ".mov", ".avi",
}
LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".cs": "C#",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".c": "C", ".h": "C/C++ Header", ".hpp": "C/C++ Header",
    ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++", ".scala": "Scala", ".sql": "SQL",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue", ".svelte": "Svelte", ".json": "JSON",
    ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML", ".xml": "XML", ".sh": "Shell", ".bat": "Batch",
    ".cmd": "Batch", ".ps1": "PowerShell", ".md": "Markdown",
}
DEFAULT_ANALYSIS_PROMPT = (
    "請先分析這個專案架構，說明入口、核心模組、主要流程、設定檔、測試位置，"
    "並指出你判斷依據來自哪些檔案。若資訊不足，請明確標示不確定。"
)
TASK_OPEN_PROJECT = "open-project"
TASK_REDOWNLOAD_MODEL = "redownload-model"


@dataclass
class ProjectFile:
    path: str
    size: int
    language: str


@dataclass
class SessionState:
    project_path: Optional[str] = None
    model_key: str = "qwen"
    model_alias: str = "qwen-local"
    summary: str = ""
    tree: List[str] = field(default_factory=list)
    files: List[ProjectFile] = field(default_factory=list)
    entrypoints: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    pinned_files: List[str] = field(default_factory=list)
    history: List[Dict[str, str]] = field(default_factory=list)
    ui_state: str = "idle"


@dataclass
class TaskState:
    id: str
    kind: str
    status: str = "pending"
    progress: int = 0
    step: str = ""
    message: str = ""
    error: Optional[Dict[str, object]] = None
    result: Optional[Dict[str, object]] = None


STATE = SessionState()
TASKS: Dict[str, TaskState] = {}
STATE_LOCK = threading.Lock()
TASK_LOCK = threading.Lock()
HF_API_HEADERS = {
    "User-Agent": "CodeWorkerWebUI/2.0",
    "Accept": "application/json",
}
DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def make_error(
    code: str,
    message: str,
    details: str = "",
    action: Optional[str] = None,
    log_path: Optional[str] = None,
    extra: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "code": code,
        "message": message,
        "details": details,
    }
    if action:
        payload["action"] = action
    if log_path:
        payload["logPath"] = log_path
    if extra:
        payload.update(extra)
    return payload


def json_response(handler: BaseHTTPRequestHandler, payload: Dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def error_response(handler: BaseHTTPRequestHandler, error: Dict[str, object], status: int = 400) -> None:
    json_response(handler, {"ok": False, "error": error}, status=status)


def text_response(handler: BaseHTTPRequestHandler, body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def normalize_path(input_path: str) -> Path:
    return Path(os.path.expandvars(input_path)).expanduser().resolve()


def create_task(kind: str) -> TaskState:
    task = TaskState(id=uuid.uuid4().hex, kind=kind)
    with TASK_LOCK:
        TASKS[task.id] = task
    return task


def update_task(task_id: str, **changes: object) -> None:
    with TASK_LOCK:
        task = TASKS[task_id]
        for key, value in changes.items():
            setattr(task, key, value)


def get_task(task_id: str) -> Optional[TaskState]:
    with TASK_LOCK:
        return TASKS.get(task_id)


def clear_session(ui_state: str = "idle") -> None:
    with STATE_LOCK:
        STATE.project_path = None
        STATE.model_key = "qwen"
        STATE.model_alias = "qwen-local"
        STATE.summary = ""
        STATE.tree = []
        STATE.files = []
        STATE.entrypoints = []
        STATE.tests = []
        STATE.pinned_files = []
        STATE.history = []
        STATE.ui_state = ui_state


def run_script(script_name: str, *args: str, timeout_seconds: Optional[int] = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return subprocess.run(
        ["cmd", "/c", str(SCRIPTS_DIR / script_name), *args],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_seconds,
        env=env,
    )


def run_script_via_log(script_name: str, *args: str, timeout_seconds: Optional[int] = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            suffix=".log",
            prefix=f"{Path(script_name).stem}-",
            dir=str(ROOT_DIR / "logs"),
            delete=False,
        ) as handle:
            temp_path = handle.name
            completed = subprocess.run(
                ["cmd", "/c", str(SCRIPTS_DIR / script_name), *args],
                cwd=str(ROOT_DIR),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout_seconds,
                env=env,
            )
        stdout = Path(temp_path).read_text(encoding="utf-8", errors="replace")
        return subprocess.CompletedProcess(
            args=completed.args,
            returncode=completed.returncode,
            stdout=stdout,
            stderr="",
        )
    except subprocess.TimeoutExpired as exc:
        output = ""
        if temp_path and Path(temp_path).exists():
            output = Path(temp_path).read_text(encoding="utf-8", errors="replace")
        raise subprocess.TimeoutExpired(exc.cmd, exc.timeout, output=output, stderr="") from exc
    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()


def load_bootstrap_manifest() -> Dict[str, object]:
    return json.loads(BOOTSTRAP_MANIFEST_PATH.read_text(encoding="utf-8"))


def get_model_manifest(model_key: str) -> Dict[str, object]:
    manifest = load_bootstrap_manifest()
    models = manifest.get("models", {})
    model = models.get(model_key)
    if not isinstance(model, dict):
        raise ValueError(f"Model config not found: {model_key}")
    return model


def is_regex_pattern(pattern: str) -> bool:
    return bool(re.search(r"[\\^$*+?{}\[\]|()]", pattern))


def resolve_huggingface_filename(repo: str, file_pattern: str) -> str:
    if not is_regex_pattern(file_pattern):
        return file_pattern

    request = urllib.request.Request(
        f"https://huggingface.co/api/models/{repo}",
        headers=HF_API_HEADERS,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.loads(response.read().decode("utf-8"))
    siblings = body.get("siblings", [])
    candidates = [
        item.get("rfilename", "")
        for item in siblings
        if isinstance(item, dict) and re.fullmatch(file_pattern, item.get("rfilename", ""))
    ]
    if not candidates:
        raise ValueError(f"No Hugging Face file matched pattern: {file_pattern}")
    return sorted(candidates)[0]


def human_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(num_bytes)} B"


def validate_model_file(model_path: Path) -> None:
    if not model_path.exists():
        raise ValueError(f"Model file not found: {model_path}")
    if not model_path.is_file():
        raise ValueError(f"Model path is not a file: {model_path}")
    size = model_path.stat().st_size
    if size <= 0:
        raise ValueError(f"Model file is empty: {model_path}")


def check_minimum_memory() -> None:
    if os.name != "nt":
        return
    command = "[int64](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    try:
        total = int(result.stdout.strip())
    except ValueError:
        return
    if total < 16 * 1024 * 1024 * 1024:
        raise RuntimeError(
            json.dumps(
                make_error(
                    "RUNTIME_INVALID",
                    "Need at least 16GB RAM.",
                    f"Detected: {total / (1024 * 1024 * 1024):.1f} GB",
                )
            )
        )


def resolve_model_details(model_key: str) -> Tuple[Path, str]:
    if model_key == "codellama":
        return ROOT_DIR / "models" / "codellama-7b-instruct-q4", "codellama-local"
    return ROOT_DIR / "models" / "qwen2.5-coder-7b-instruct-q4", "qwen-local"


def find_model_file(model_dir: Path) -> Optional[Path]:
    matches = sorted(model_dir.glob("*.gguf"))
    return matches[0] if matches else None


def query_models(port: int, timeout_sec: int = 2) -> Optional[Dict[str, object]]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def is_model_ready(model_alias: str, port: int) -> bool:
    payload = query_models(port)
    if not payload:
        return False
    data = payload.get("data", [])
    return any(isinstance(item, dict) and item.get("id") == model_alias for item in data)


def is_port_listening(port: int) -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"try {{ $listener = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction Stop; if ($listener) {{ exit 0 }} else {{ exit 1 }} }} catch {{ exit 1 }}",
        ],
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def ensure_runtime_and_model(model_key: str) -> Tuple[Path, str]:
    llama_server = ROOT_DIR / "runtime" / "llama.cpp" / "llama-server.exe"
    if not llama_server.exists():
        runtime = run_script("bootstrap.cmd", "-SkipModels", timeout_seconds=300)
        if runtime.returncode != 0 or not llama_server.exists():
            raise RuntimeError(
                json.dumps(
                    make_error(
                        "RUNTIME_MISSING",
                        "Failed to prepare llama.cpp runtime.",
                        runtime.stdout + runtime.stderr,
                    )
                )
            )

    model_dir, model_alias = resolve_model_details(model_key)
    model_file = find_model_file(model_dir)
    if model_file is None:
        bootstrap = run_script("bootstrap.cmd", "-SkipRuntime", "-Models", model_key, timeout_seconds=1800)
        model_file = find_model_file(model_dir)
        if bootstrap.returncode != 0 or model_file is None:
            raise RuntimeError(
                json.dumps(
                    make_error(
                        "MODEL_MISSING",
                        "Failed to prepare model.",
                        bootstrap.stdout + bootstrap.stderr,
                        extra={"modelKey": model_key},
                    )
                )
            )
    validate_model_file(model_file)
    return model_file, model_alias


def ensure_local_model_server(model_key: str, port: int = 8080) -> Dict[str, object]:
    if model_key not in {"qwen", "codellama"}:
        raise RuntimeError(json.dumps(make_error("MODEL_START_FAILED", "Unknown model.", model_key)))

    check_minimum_memory()
    model_file, model_alias = ensure_runtime_and_model(model_key)
    llama_server = ROOT_DIR / "runtime" / "llama.cpp" / "llama-server.exe"

    if is_model_ready(model_alias, port):
        return {"modelAlias": model_alias, "logPath": None, "alreadyRunning": True}

    if is_port_listening(port):
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_START_FAILED",
                    "Port is already in use.",
                    f"Port {port} is occupied by another process.",
                    extra={"modelKey": model_key},
                )
            )
        )

    stamp = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "[DateTime]::Now.ToString('yyyyMMdd-HHmmss')"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    ).stdout.strip() or "unknown"
    log_path = ROOT_DIR / "logs" / f"llama-server-{model_key}-{stamp}.log"

    with open(log_path, "ab") as log_handle:
        subprocess.Popen(
            [
                str(llama_server),
                "--host", "127.0.0.1",
                "--port", str(port),
                "--alias", model_alias,
                "-m", str(model_file),
                "-c", "8192",
                "--threads", str(os.cpu_count() or 4),
                "--n-gpu-layers", "0",
            ],
            cwd=str(ROOT_DIR),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=DETACHED_FLAGS,
            close_fds=True,
        )

    for _ in range(60):
        if is_model_ready(model_alias, port):
            return {"modelAlias": model_alias, "logPath": str(log_path), "alreadyRunning": False}
        threading.Event().wait(2)

    details = ""
    if log_path.exists():
        details = log_path.read_text(encoding="utf-8", errors="replace")[-6000:]
    raise RuntimeError(
        json.dumps(
            make_error(
                "MODEL_START_FAILED",
                "Server failed to become ready.",
                details or str(log_path),
                log_path=str(log_path),
                extra={"modelKey": model_key},
            )
        )
    )


def download_model_with_progress(task_id: str, model_key: str) -> Tuple[Path, int]:
    model_config = get_model_manifest(model_key)
    if not model_config.get("enabled", False):
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_INVALID",
                    "Model is disabled in bootstrap manifest.",
                    f"modelKey={model_key}",
                    extra={"modelKey": model_key},
                )
            )
        )
    if model_config.get("provider") != "huggingface":
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_DOWNLOAD_FAILED",
                    "Only Hugging Face model downloads are supported in the web UI.",
                    f"provider={model_config.get('provider', '')}",
                    extra={"modelKey": model_key},
                )
            )
        )

    repo = str(model_config.get("repo", "")).strip()
    file_pattern = str(model_config.get("filePattern", "")).strip()
    target_dir = ROOT_DIR / str(model_config.get("targetDir", "")).strip()
    if not repo or not file_pattern or not str(model_config.get("targetDir", "")).strip():
        raise RuntimeError(
            json.dumps(
                make_error(
                    "MODEL_INVALID",
                    "Model manifest is incomplete.",
                    f"repo={repo}, filePattern={file_pattern}, targetDir={model_config.get('targetDir', '')}",
                    extra={"modelKey": model_key},
                )
            )
        )

    update_task(task_id, progress=8, step="解析模型來源", message="正在取得模型檔資訊")
    filename = resolve_huggingface_filename(repo, file_pattern)
    download_url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(filename)}?download=true"

    target_dir.mkdir(parents=True, exist_ok=True)
    final_path = target_dir / Path(filename).name
    part_path = final_path.with_suffix(final_path.suffix + ".part")
    if part_path.exists():
        part_path.unlink()

    update_task(task_id, progress=12, step="準備下載", message=f"即將下載 {final_path.name}")
    request = urllib.request.Request(download_url, headers=HF_API_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            content_length = response.headers.get("Content-Length")
            total_bytes = int(content_length) if content_length and content_length.isdigit() else 0
            bytes_written = 0
            chunk_size = 1024 * 1024
            with open(part_path, "wb") as handle:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    handle.write(chunk)
                    bytes_written += len(chunk)
                    if total_bytes > 0:
                        progress = 12 + int((bytes_written / total_bytes) * 83)
                        progress = max(12, min(progress, 95))
                        message = f"已下載 {human_size(bytes_written)} / {human_size(total_bytes)}"
                    else:
                        progress = 12
                        message = f"已下載 {human_size(bytes_written)}"
                    update_task(task_id, progress=progress, step="重新下載模型", message=message)

        if final_path.exists():
            final_path.unlink()
        os.replace(part_path, final_path)
        validate_model_file(final_path)
        return final_path, final_path.stat().st_size
    except Exception:
        if part_path.exists():
            part_path.unlink()
        raise


def choose_folder() -> Dict[str, object]:
    tkinter_script = """
import json
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.lift()
root.update()
selected = filedialog.askdirectory(
    parent=root,
    title="選擇專案資料夾",
    mustexist=True,
) or ""
print(json.dumps({"path": selected}))
root.destroy()
"""
    picker_env = os.environ.copy()
    picker_env["PYTHONIOENCODING"] = "utf-8"
    picker_env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", tkinter_script],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
        env=picker_env,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(details or "Folder picker process failed.")
    try:
        payload = json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(result.stdout.strip() or "Folder picker returned invalid payload.") from exc
    selected = str(payload.get("path", "")).strip()
    return {"canceled": not bool(selected), "path": selected}


def collect_project_files(project_root: Path) -> List[ProjectFile]:
    results: List[ProjectFile] = []
    ignored_dirs = {item.lower() for item in IGNORED_DIRS}
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [item for item in dirs if item.lower() not in ignored_dirs]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() in IGNORED_EXTENSIONS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size > 512_000:
                continue
            results.append(
                ProjectFile(
                    path=path.relative_to(project_root).as_posix(),
                    size=stat.st_size,
                    language=LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "Other"),
                )
            )
            if len(results) >= MAX_SCAN_FILES:
                return sorted(results, key=lambda item: item.path.lower())
    return sorted(results, key=lambda item: item.path.lower())


def detect_entrypoints(file_paths: List[str]) -> List[str]:
    patterns = [
        r"(^|/)(package\.json|pyproject\.toml|requirements\.txt|go\.mod|cargo\.toml|pom\.xml|build\.gradle|build\.gradle\.kts)$",
        r"(^|/)(app|main|index|server|manage)\.(py|js|ts|tsx|jsx|go|rs|php|rb|cs|java)$",
        r"(^|/)src/(main|index|app|server)\.(ts|tsx|js|jsx|py|go|rs)$",
    ]
    return [path for path in file_paths if any(re.search(pattern, path.lower()) for pattern in patterns)][:12]


def detect_test_locations(file_paths: List[str]) -> List[str]:
    return [
        path for path in file_paths
        if any(token in path.lower() for token in ["/test", "/tests", "__tests__", ".spec.", ".test."])
    ][:20]


def language_breakdown(files: List[ProjectFile]) -> List[str]:
    counts: Dict[str, int] = {}
    for file in files:
        counts[file.language] = counts.get(file.language, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [f"{name}: {count}" for name, count in ordered[:10]]


def build_summary(project_root: Path, files: List[ProjectFile], entrypoints: List[str], tests: List[str]) -> str:
    total_size = sum(file.size for file in files)
    lines = [
        f"專案路徑: {project_root}",
        f"檔案數量(已掃描): {len(files)}",
        f"估計文字檔總大小: {total_size} bytes",
        "主要語言: " + (", ".join(language_breakdown(files)) if files else "無"),
        "可能入口檔案: " + (", ".join(entrypoints[:8]) if entrypoints else "未明確找到"),
        "測試相關檔案: " + (", ".join(tests[:8]) if tests else "未明確找到"),
    ]
    return "\n".join(lines)


def read_file_excerpt(project_root: Path, relative_path: str, max_chars: int = MAX_FILE_CHARS) -> str:
    target = (project_root / relative_path).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("Invalid file path.") from exc
    content = target.read_text(encoding="utf-8", errors="replace")
    return content[:max_chars] + ("\n... [truncated]" if len(content) > max_chars else "")


def choose_context_files(message: str, files: List[ProjectFile], entrypoints: List[str], tests: List[str], pinned: List[str]) -> List[str]:
    lowered = message.lower()
    tokens = {token for token in re.split(r"[^a-zA-Z0-9_./-]+", lowered) if len(token) >= 2}
    scores: Dict[str, int] = {}
    for path in pinned:
        scores[path] = scores.get(path, 0) + 100
    for path in entrypoints:
        scores[path] = scores.get(path, 0) + 30
    for path in tests[:5]:
        scores[path] = scores.get(path, 0) + 10
    for file in files:
        path_lower = file.path.lower()
        score = scores.get(file.path, 0)
        if any(token in path_lower for token in tokens):
            score += 20
        if Path(file.path).name.lower() in lowered:
            score += 25
        if score > 0:
            scores[file.path] = score
    ranked = [path for path, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]
    if not ranked:
        ranked = entrypoints[:4] + tests[:2]
    unique: List[str] = []
    seen = set()
    for path in ranked:
        if path not in seen:
            unique.append(path)
            seen.add(path)
        if len(unique) >= MAX_CONTEXT_FILES:
            break
    return unique


def build_project_context(project_root: Path, state: SessionState, message: str) -> str:
    selected_paths = choose_context_files(message, state.files, state.entrypoints, state.tests, state.pinned_files)
    chunks = [state.summary, "檔案樹(節錄):\n" + "\n".join(state.tree[:MAX_TREE_CONTEXT_ITEMS])]
    total_chars = sum(len(chunk) for chunk in chunks)
    for relative_path in selected_paths:
        try:
            excerpt = read_file_excerpt(project_root, relative_path)
        except (OSError, ValueError):
            continue
        block = f"\n檔案: {relative_path}\n```\n{excerpt}\n```"
        if total_chars + len(block) > MAX_TOTAL_CONTEXT:
            break
        chunks.append(block)
        total_chars += len(block)
    return "\n\n".join(chunks)


def call_local_model(model_alias: str, messages: List[Dict[str, str]]) -> str:
    payload = json.dumps(
        {"model": model_alias, "messages": messages, "temperature": 0.2, "stream": False},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        LLM_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8", errors="replace")
        except Exception:
            details = str(exc)
        if exc.code == 400 and "exceeds the available context size" in details:
            raise RuntimeError(
                "目前送給模型的專案上下文太大，超過本機模型的 8192 token 上限。請縮小對話歷史、減少釘選檔案，或重新開啟專案後再試。"
            ) from exc
        raise RuntimeError(f"Failed to call local model endpoint: HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to call local model endpoint: {exc}") from exc
    try:
        return body["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected model response format.") from exc


def parse_script_output(output: str) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    for line in output.splitlines():
        if line.startswith("[ERROR_CODE] "):
            metadata["code"] = line[len("[ERROR_CODE] "):].strip()
        elif line.startswith("[ERROR_MESSAGE] "):
            metadata["message"] = line[len("[ERROR_MESSAGE] "):].strip()
        elif line.startswith("[ERROR_DETAILS] "):
            metadata["details"] = line[len("[ERROR_DETAILS] "):].strip()
        elif line.startswith("[LOG_FILE] "):
            metadata["logPath"] = line[len("[LOG_FILE] "):].strip()
    return metadata


def classify_start_server_error(output: str, model_key: str) -> Dict[str, object]:
    info = parse_script_output(output)
    code = info.get("code", "MODEL_START_FAILED")
    message = info.get("message", "Failed to start model service.")
    details = info.get("details", output.strip())
    action = None
    if code == "MODEL_INVALID":
        action = "redownload-model"
    return make_error(
        code=code,
        message=message,
        details=details,
        action=action,
        log_path=info.get("logPath"),
        extra={"modelKey": model_key},
    )


def build_session_payload(project_root: Path, model_key: str) -> Dict[str, object]:
    files = collect_project_files(project_root)
    file_paths = [file.path for file in files]
    entrypoints = detect_entrypoints(file_paths)
    tests = detect_test_locations(file_paths)
    summary = build_summary(project_root, files, entrypoints, tests)
    tree = file_paths[:MAX_TREE_ITEMS]
    model_alias = "codellama-local" if model_key == "codellama" else "qwen-local"
    with STATE_LOCK:
        STATE.project_path = str(project_root)
        STATE.model_key = model_key
        STATE.model_alias = model_alias
        STATE.summary = summary
        STATE.tree = tree
        STATE.files = files
        STATE.entrypoints = entrypoints
        STATE.tests = tests
        STATE.pinned_files = []
        STATE.history = []
        STATE.ui_state = "ready"
    return {
        "projectPath": str(project_root),
        "modelKey": model_key,
        "modelAlias": model_alias,
        "summary": summary,
        "tree": tree,
        "entrypoints": entrypoints,
        "tests": tests,
        "fileCount": len(files),
        "uiState": "ready",
    }


def open_project_worker(task_id: str, project_path: str, model_key: str) -> None:
    clear_session(ui_state="opening")
    try:
        update_task(task_id, status="running", progress=10, step="驗證專案路徑", message="正在檢查專案路徑")
        project_root = normalize_path(project_path)
        if not project_root.exists() or not project_root.is_dir():
            raise ValueError(f"Project directory not found: {project_root}")

        update_task(task_id, progress=25, step="準備 Git 工作區", message="正在初始化或檢查 git repository")
        attach = run_script("attach-project.cmd", str(project_root), timeout_seconds=ATTACH_PROJECT_TIMEOUT_SECONDS)
        if attach.returncode != 0:
            raise RuntimeError(json.dumps(make_error("GIT_INIT_FAILED", "Failed to prepare git repository.", attach.stdout + attach.stderr)))

        update_task(task_id, progress=45, step="Git 工作區完成", message="已完成 git 初始化與基線快照")
        update_task(task_id, progress=55, step="啟動本地模型", message="正在驗證模型並啟動 llama-server")
        ensure_local_model_server(model_key, port=8080)

        update_task(task_id, progress=85, step="索引專案", message="正在掃描檔案、入口與測試位置")
        result = build_session_payload(project_root, model_key)
        update_task(task_id, status="completed", progress=100, step="完成", message="專案已開啟", result=result)
    except ValueError as exc:
        clear_session(ui_state="error")
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="開啟專案失敗",
            error=make_error("PROJECT_PATH_INVALID", "Project path is invalid.", str(exc)),
        )
    except RuntimeError as exc:
        clear_session(ui_state="error")
        error_payload: Dict[str, object]
        try:
            error_payload = json.loads(str(exc))
        except json.JSONDecodeError:
            error_payload = make_error("MODEL_START_FAILED", "Open project failed.", str(exc))
        update_task(task_id, status="failed", progress=100, step="失敗", message="開啟專案失敗", error=error_payload)
    except subprocess.TimeoutExpired as exc:
        clear_session(ui_state="error")
        command = " ".join(str(part) for part in exc.cmd) if exc.cmd else ""
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        if "attach-project.cmd" in command:
            error_payload = make_error(
                "GIT_INIT_FAILED",
                "Preparing git repository timed out.",
                "attach-project.cmd 超過等待時間。資料夾可能過大、含大量資源檔，或 git commit 被互動式設定卡住。\n\n"
                + (stdout + stderr).strip(),
            )
        else:
            error_payload = make_error(
                "MODEL_START_FAILED",
                "Starting local model timed out.",
                "start-server.cmd 超過等待時間。請檢查 logs 目錄中的 llama-server log。\n\n"
                + (stdout + stderr).strip(),
            )
        update_task(task_id, status="failed", progress=100, step="失敗", message="開啟專案失敗", error=error_payload)
    except Exception as exc:
        clear_session(ui_state="error")
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="開啟專案失敗",
            error=make_error("INDEX_FAILED", "Unexpected error while opening project.", traceback.format_exc()),
        )


def redownload_model_worker(task_id: str, model_key: str) -> None:
    try:
        update_task(task_id, status="running", progress=3, step="驗證模型", message="正在確認模型設定")
        if model_key not in {"qwen", "codellama"}:
            raise RuntimeError(json.dumps(make_error("MODEL_INVALID", "Unsupported model.", model_key)))

        model_path, model_size = download_model_with_progress(task_id, model_key)

        update_task(
            task_id,
            status="completed",
            progress=100,
            step="完成",
            message="模型重新下載完成",
            result={
                "modelKey": model_key,
                "modelPath": str(model_path),
                "modelSize": model_size,
            },
        )
    except ValueError as exc:
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="模型重新下載失敗",
            error=make_error("MODEL_INVALID", "Model validation failed.", str(exc), extra={"modelKey": model_key}),
        )
    except urllib.error.HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8", errors="replace")
        except Exception:
            details = str(exc)
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="模型重新下載失敗",
            error=make_error("MODEL_DOWNLOAD_FAILED", "Failed to download model.", details or str(exc), extra={"modelKey": model_key}),
        )
    except RuntimeError as exc:
        try:
            error_payload = json.loads(str(exc))
        except json.JSONDecodeError:
            error_payload = make_error("MODEL_DOWNLOAD_FAILED", "Failed to redownload model.", str(exc))
        update_task(task_id, status="failed", progress=100, step="失敗", message="模型重新下載失敗", error=error_payload)
    except Exception:
        update_task(
            task_id,
            status="failed",
            progress=100,
            step="失敗",
            message="模型重新下載失敗",
            error=make_error("MODEL_DOWNLOAD_FAILED", "Unexpected error while redownloading model.", traceback.format_exc(), extra={"modelKey": model_key}),
        )


def start_background_task(kind: str, worker, *args: str) -> TaskState:
    task = create_task(kind)
    thread = threading.Thread(target=worker, args=(task.id, *args), daemon=True)
    thread.start()
    return task


def get_status_payload() -> Dict[str, object]:
    with STATE_LOCK:
        return {
            "projectPath": STATE.project_path,
            "modelKey": STATE.model_key,
            "modelAlias": STATE.model_alias,
            "summary": STATE.summary,
            "tree": STATE.tree,
            "entrypoints": STATE.entrypoints,
            "tests": STATE.tests,
            "pinnedFiles": STATE.pinned_files,
            "history": STATE.history[-20:],
            "uiState": STATE.ui_state,
        }


class WebUIHandler(BaseHTTPRequestHandler):
    server_version = "CodeWorkerWebUI/2.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.serve_static("index.html")
            return
        if parsed.path == "/api/status":
            json_response(self, {"ok": True, "data": get_status_payload()})
            return
        if parsed.path == "/api/file":
            self.handle_file_request(parsed)
            return
        if parsed.path.startswith("/api/tasks/"):
            self.handle_task_status(parsed.path)
            return
        self.serve_static(parsed.path.lstrip("/"))

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/pick-folder":
            self.handle_pick_folder()
            return
        if parsed.path == "/api/tasks/open-project":
            self.handle_open_project_task()
            return
        if parsed.path == "/api/models/redownload":
            self.handle_redownload_model()
            return
        if parsed.path == "/api/analyze":
            self.handle_analyze()
            return
        if parsed.path == "/api/chat":
            self.handle_chat()
            return
        if parsed.path == "/api/pin-files":
            self.handle_pin_files()
            return
        if parsed.path == "/api/reset-history":
            self.handle_reset_history()
            return
        error_response(self, make_error("NOT_FOUND", "Not found."), status=404)

    def log_message(self, format: str, *args) -> None:
        return

    def serve_static(self, relative_path: str) -> None:
        safe_path = (STATIC_DIR / relative_path).resolve()
        if not str(safe_path).startswith(str(STATIC_DIR)) or not safe_path.exists() or safe_path.is_dir():
            error_response(self, make_error("NOT_FOUND", "Not found."), status=404)
            return
        content_type, _ = mimetypes.guess_type(str(safe_path))
        text_response(self, safe_path.read_text(encoding="utf-8"), 200, (content_type or "text/plain") + "; charset=utf-8")

    def read_json_body(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def handle_task_status(self, path: str) -> None:
        task_id = path.rsplit("/", 1)[-1]
        task = get_task(task_id)
        if not task:
            error_response(self, make_error("TASK_NOT_FOUND", "Task not found."), status=404)
            return
        json_response(self, {"ok": True, "data": asdict(task)})

    def handle_pick_folder(self) -> None:
        try:
            result = choose_folder()
            json_response(self, {"ok": True, "data": result})
        except Exception as exc:
            error_response(self, make_error("PICK_FOLDER_FAILED", "Failed to open folder picker.", str(exc)))

    def handle_open_project_task(self) -> None:
        try:
            payload = self.read_json_body()
            project_path = str(payload.get("projectPath", "")).strip()
            model_key = str(payload.get("modelKey", "qwen")).strip().lower()
            if model_key not in {"qwen", "codellama"}:
                raise ValueError("Unsupported model. Use qwen or codellama.")
            if not project_path:
                raise ValueError("Project path is required.")
            task = start_background_task(TASK_OPEN_PROJECT, open_project_worker, project_path, model_key)
            json_response(self, {"ok": True, "data": {"taskId": task.id, "kind": task.kind}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_PATH_INVALID", "Project path is invalid.", str(exc)))

    def handle_redownload_model(self) -> None:
        try:
            payload = self.read_json_body()
            model_key = str(payload.get("modelKey", "qwen")).strip().lower()
            task = start_background_task(TASK_REDOWNLOAD_MODEL, redownload_model_worker, model_key)
            json_response(self, {"ok": True, "data": {"taskId": task.id, "kind": task.kind}})
        except Exception as exc:
            error_response(self, make_error("MODEL_DOWNLOAD_FAILED", "Failed to start model redownload.", str(exc)))

    def handle_analyze(self) -> None:
        try:
            payload = self.read_json_body()
            prompt = str(payload.get("prompt", DEFAULT_ANALYSIS_PROMPT)).strip() or DEFAULT_ANALYSIS_PROMPT
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("請先完成開啟專案。")
                project_root = Path(STATE.project_path)
                context = build_project_context(project_root, STATE, prompt)
                model_alias = STATE.model_alias
            messages = [
                {"role": "system", "content": "你是本機離線 code assistant。請使用繁體中文回答，並根據提供的專案上下文分析；若資訊不足請直接說不確定。"},
                {"role": "user", "content": f"{prompt}\n\n以下是專案上下文：\n{context}"},
            ]
            reply = call_local_model(model_alias, messages)
            with STATE_LOCK:
                STATE.history.append({"role": "assistant", "content": reply, "kind": "analysis"})
            json_response(self, {"ok": True, "data": {"reply": reply}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Project is not ready.", str(exc)))
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Analyze failed.", str(exc)))

    def handle_chat(self) -> None:
        try:
            payload = self.read_json_body()
            message = str(payload.get("message", "")).strip()
            if not message:
                raise ValueError("message is required.")
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("請先完成開啟專案。")
                project_root = Path(STATE.project_path)
                context = build_project_context(project_root, STATE, message)
                history = STATE.history[-MAX_CHAT_HISTORY_ITEMS:]
                model_alias = STATE.model_alias
            messages = [
                {"role": "system", "content": "你是本機離線 code assistant。請使用繁體中文回答，回答時盡量引用具體檔案路徑。若還需要更多檔案才足以判斷，請直接指出。"},
                {"role": "system", "content": f"目前專案上下文如下：\n{context}"},
            ]
            for item in history:
                if item.get("role") in {"user", "assistant"} and item.get("content"):
                    messages.append({"role": item["role"], "content": item["content"]})
            messages.append({"role": "user", "content": message})
            reply = call_local_model(model_alias, messages)
            with STATE_LOCK:
                STATE.history.append({"role": "user", "content": message, "kind": "chat"})
                STATE.history.append({"role": "assistant", "content": reply, "kind": "chat"})
            json_response(self, {"ok": True, "data": {"reply": reply}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Project is not ready.", str(exc)))
        except Exception as exc:
            error_response(self, make_error("MODEL_START_FAILED", "Chat failed.", str(exc)))

    def handle_pin_files(self) -> None:
        try:
            payload = self.read_json_body()
            files = payload.get("files", [])
            if not isinstance(files, list):
                raise ValueError("files must be a list.")
            with STATE_LOCK:
                if STATE.ui_state != "ready":
                    raise ValueError("Project is not ready.")
                allowed = {file.path for file in STATE.files}
                pinned = [path for path in files if isinstance(path, str) and path in allowed][:8]
                STATE.pinned_files = pinned
            json_response(self, {"ok": True, "data": {"pinnedFiles": pinned}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Project is not ready.", str(exc)))

    def handle_reset_history(self) -> None:
        with STATE_LOCK:
            STATE.history = []
        json_response(self, {"ok": True, "data": {"history": []}})

    def handle_file_request(self, parsed: urllib.parse.ParseResult) -> None:
        try:
            query = urllib.parse.parse_qs(parsed.query)
            relative_path = query.get("path", [""])[0]
            if not relative_path:
                raise ValueError("path is required.")
            with STATE_LOCK:
                if STATE.ui_state != "ready" or not STATE.project_path:
                    raise ValueError("Project is not ready.")
                project_root = Path(STATE.project_path)
                if relative_path not in {file.path for file in STATE.files}:
                    raise ValueError("File is not part of the indexed project.")
            content = read_file_excerpt(project_root, relative_path, max_chars=12000)
            json_response(self, {"ok": True, "data": {"path": relative_path, "content": content}})
        except ValueError as exc:
            error_response(self, make_error("PROJECT_NOT_READY", "Cannot preview file.", str(exc)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8764, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), WebUIHandler)
    print(f"CodeWorker Web UI running at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
