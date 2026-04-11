"""
Internal benchmark utility for CodeWorker model context validation.

Purpose:
- measure the practical context ceiling of each local model on the current machine
- compare startup stability, completion success, and structured-output reliability
- generate machine-readable and human-readable artifacts for internal evaluation

Primary outputs:
- logs/model-context-bench.json
- logs/model-context-summary.md

This script is for internal benchmarking and regression tracking.
It is not part of the normal end-user workflow.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
START_SERVER = ROOT_DIR / "scripts" / "start-server.cmd"
GAME_DIR = Path(r"C:\Games")
MODELS = ("qwen35", "gemma4")
CONTEXTS = (8192, 12288, 16384)
PORT_BASE = {
    "qwen35": 18080,
    "gemma4": 18180,
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    tail = limit - head - 20
    return text[:head] + "\n...\n[truncated]\n...\n" + text[-tail:]


def extract_window(content: str, keyword: str, radius: int = 1800) -> str:
    idx = content.find(keyword)
    if idx < 0:
        return truncate(content, radius * 2)
    start = max(0, idx - radius)
    end = min(len(content), idx + radius)
    return content[start:end].strip()


def build_project_context() -> str:
    program = read_text(GAME_DIR / "Program.cs")
    form1 = read_text(GAME_DIR / "Form1.cs")
    audio = read_text(GAME_DIR / "AudioManager.cs")
    parts = [
        "Project excerpts:",
        "檔案: Program.cs\n```csharp\n" + truncate(program, 1800) + "\n```",
        "檔案: Form1.cs\n```csharp\n" + truncate(extract_window(form1, "Form1_KeyDown"), 4200) + "\n```",
        "檔案: AudioManager.cs\n```csharp\n" + truncate(audio, 2600) + "\n```",
    ]
    return "\n\n".join(parts)


PROJECT_CONTEXT = build_project_context()


def kill_port(port: int) -> None:
    command = (
        "Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique"
    ).format(port=port)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    pids = [line.strip() for line in result.stdout.splitlines() if line.strip().isdigit()]
    for pid in pids:
        subprocess.run(
            ["taskkill", "/PID", pid, "/F"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=15,
        )
    if pids:
        time.sleep(2)


def kill_bench_ports() -> None:
    for base in PORT_BASE.values():
        for offset in range(8):
            kill_port(base + offset)


def request_chat(port: int, model: str, messages, max_tokens: int, timeout: int = 180):
    try:
        from webui import server as web_server  # type: ignore
        prepared = web_server.prepare_messages_for_model(model, messages)
    except Exception:
        prepared = messages
    payload = json.dumps(
        {
            "model": model,
            "messages": prepared,
            "temperature": 0.2,
            "stream": False,
            "max_tokens": max_tokens,
            **({"chat_template_kwargs": {"enable_thinking": False}} if model == "qwen35-local" else {}),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            choice = body["choices"][0]
            content = str(choice["message"]["content"])
            finish_reason = str(choice.get("finish_reason", "") or "")
            try:
                from webui import server as web_server  # type: ignore
                content = web_server.sanitize_model_reply(model, content)
            except Exception:
                content = content.strip()
            return {"ok": True, "reply": content, "finish_reason": finish_reason, "length": len(content)}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {exc.code}: {details}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def probe_model(model_key: str, context_size: int, port: int, include_structured: bool = True):
    kill_bench_ports()
    start = subprocess.run(
        ["cmd", "/c", str(START_SERVER), model_key, str(port), str(context_size)],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=420,
    )
    result = {
        "startup_ok": start.returncode == 0,
        "startup_output": (start.stdout + start.stderr).strip(),
        "port": port,
        "context": context_size,
        "tests": {},
    }
    if start.returncode != 0:
        return result

    tests = {
        "entry": {
            "messages": [
                {"role": "system", "content": "請使用繁體中文直接回答重點。"},
                {"role": "user", "content": PROJECT_CONTEXT + "\n\n問題：專案入口在哪裡？請只回答檔案名稱與一句理由。"},
            ],
            "max_tokens": 320,
            "timeout": 90,
        },
        "analysis": {
            "messages": [
                {"role": "system", "content": "請使用繁體中文直接回答重點，不要重述問題。"},
                {"role": "user", "content": PROJECT_CONTEXT + "\n\n問題：請告訴我這個程式的功能與操作方式，先給結論，再用 4 點說明。"},
            ],
            "max_tokens": 1400,
            "timeout": 180,
        },
    }
    if include_structured:
        tests["structured"] = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "請使用繁體中文，但只輸出 JSON，不要輸出 markdown。"
                        "JSON key 固定為 summary,path,target,reason,before,after,notes。"
                        "只允許一個 path。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        PROJECT_CONTEXT
                        + "\n\n需求：我要按下 M 鍵切換背景音樂靜音，請只根據目前檔案提供局部修改建議，不要重寫整檔。"
                    ),
                },
            ],
            "max_tokens": 900,
            "timeout": 180,
        }
    

    model_alias = {"qwen35": "qwen35-local", "gemma4": "gemma4-local"}[model_key]
    for name, spec in tests.items():
        reply = request_chat(port, model_alias, spec["messages"], spec["max_tokens"], timeout=spec.get("timeout", 180))
        result["tests"][name] = reply
    return result


def build_summary(results):
    lines = ["# Model Context Bench", ""]
    for model_key in MODELS:
        model_results = [item for item in results if item["model"] == model_key]
        lines.append(f"## {model_key}")
        successful = [item for item in model_results if item["startup_ok"] and all(test.get("ok") for test in item["tests"].values())]
        if successful:
            best = max(successful, key=lambda item: item["context"])
            lines.append(f"- 穩定可用 context：`{best['context']}`")
        else:
            lines.append("- 穩定可用 context：`未完成`")
        for item in model_results:
            status = "ok" if item["startup_ok"] and all(test.get("ok") for test in item["tests"].values()) else "fail"
            lines.append(f"- {item['context']}: {status}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--contexts", nargs="+", type=int, default=list(CONTEXTS))
    parser.add_argument("--skip-structured", action="store_true")
    args = parser.parse_args()

    selected_models = [model for model in args.models if model in MODELS]
    selected_contexts = [context for context in args.contexts if context > 0]
    if not selected_models:
        raise SystemExit("No valid models selected.")
    if not selected_contexts:
        raise SystemExit("No valid contexts selected.")

    results = []
    for model_key in selected_models:
        for index, context_size in enumerate(selected_contexts):
            port = PORT_BASE[model_key] + index
            item = probe_model(model_key, context_size, port, include_structured=not args.skip_structured)
            item["model"] = model_key
            results.append(item)
    logs_dir = ROOT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "model-context-bench.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (logs_dir / "model-context-summary.md").write_text(build_summary(results), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
