"""
Internal benchmark utility for CodeWorker model context validation.

Purpose:
- measure the practical context ceiling of each local model on the current machine
- compare startup stability, completion success, and structured-output reliability
- generate machine-readable and human-readable artifacts for internal evaluation

Primary outputs:
- logs/model-context-bench.json
- logs/model-context-summary.md
- data/model-context-calibration.json

This script is for internal benchmarking and regression tracking.
It is not part of the normal end-user workflow.
"""

import argparse
import datetime as dt
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
try:
    from webui import server as web_server  # type: ignore
    MODELS = tuple(sorted(web_server.SUPPORTED_MODEL_KEYS))
except Exception:
    web_server = None  # type: ignore
    MODELS = ("qwen35", "gemma4", "qwen36a3b")
CONTEXTS = (4096, 8192, 16384, 32768, 65536, 131072, 262144)
PORT_BASE = {model: 18080 + (index * 20) for index, model in enumerate(MODELS)}


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
            **({"chat_template_kwargs": {"enable_thinking": False}} if str(model).startswith("qwen") else {}),
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


def request_json(port: int, path: str, timeout: int = 30):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as response:
            return {"ok": True, "data": json.loads(response.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_model_alias(model_key: str) -> str:
    if web_server is not None:
        return web_server.get_model_alias(model_key)
    return {"qwen35": "qwen35-local", "gemma4": "gemma4-local", "qwen36a3b": "qwen36a3b-local"}.get(model_key, f"{model_key}-local")


def get_default_model_port(model_key: str) -> int:
    if web_server is not None:
        return int(web_server.get_model_port(model_key))
    return {"gemma4": 8081, "qwen35": 8082, "qwen36a3b": 8087}.get(model_key, 8080)


def response_contains_model(payload, model_alias: str) -> bool:
    if not isinstance(payload, dict):
        return False
    candidates = []
    for key in ("data", "models"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    for item in candidates:
        if not isinstance(item, dict):
            continue
        names = [
            str(item.get("id", "")),
            str(item.get("model", "")),
            str(item.get("name", "")),
        ]
        aliases = item.get("aliases")
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        if model_alias in names:
            return True
    return False


def extract_reported_context(props) -> int:
    if not isinstance(props, dict) or not props.get("ok"):
        return 0
    settings = props.get("data", {}).get("default_generation_settings", {})
    try:
        return int(settings.get("n_ctx") or 0)
    except (TypeError, ValueError):
        return 0


def existing_server_port_for_context(model_key: str, context_size: int) -> int:
    model_alias = get_model_alias(model_key)
    port = get_default_model_port(model_key)
    models = request_json(port, "/v1/models", timeout=5)
    if not models.get("ok") or not response_contains_model(models.get("data"), model_alias):
        return 0
    reported_context = extract_reported_context(request_json(port, "/props", timeout=5))
    if reported_context and reported_context >= int(context_size):
        return port
    return 0


def build_tests(include_structured: bool = True):
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
            "max_tokens": 360,
            "timeout": 90,
        }
    return tests


def run_probe_tests(result, model_key: str, port: int, include_structured: bool = True):
    result["models_endpoint"] = request_json(port, "/v1/models")
    props = request_json(port, "/props")
    result["props"] = props
    reported_context = extract_reported_context(props)
    if reported_context:
        result["reported_n_ctx"] = reported_context
    model_alias = get_model_alias(model_key)
    for name, spec in build_tests(include_structured=include_structured).items():
        reply = request_chat(port, model_alias, spec["messages"], spec["max_tokens"], timeout=spec.get("timeout", 180))
        result["tests"][name] = reply
    return result


def probe_model(model_key: str, context_size: int, port: int, include_structured: bool = True):
    existing_port = existing_server_port_for_context(model_key, context_size)
    if existing_port:
        result = {
            "startup_ok": True,
            "startup_output": f"Reused existing {model_key} server on port {existing_port}.",
            "port": existing_port,
            "context": context_size,
            "tests": {},
            "reused_existing_server": True,
        }
        return run_probe_tests(result, model_key, existing_port, include_structured=include_structured)

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
    startup_output = (start.stdout + start.stderr).strip()
    startup_ok = start.returncode == 0 and "[ERROR_CODE]" not in startup_output
    result = {
        "startup_ok": startup_ok,
        "startup_output": startup_output,
        "port": port,
        "context": context_size,
        "tests": {},
    }
    if not startup_ok:
        return result

    return run_probe_tests(result, model_key, port, include_structured=include_structured)


def build_summary(results, selected_models=None):
    lines = ["# Model Context Bench", ""]
    selected = list(selected_models or MODELS)
    for model_key in selected:
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
            reported = item.get("reported_n_ctx")
            suffix = f" (reported n_ctx `{reported}`)" if reported is not None else ""
            lines.append(f"- {item['context']}: {status}{suffix}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_calibration(results, selected_models=None):
    measured_at = dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")
    calibration = {}
    selected = list(selected_models or MODELS)
    for model_key in selected:
        model_results = [item for item in results if item["model"] == model_key]
        successful = [item for item in model_results if item["startup_ok"] and all(test.get("ok") for test in item["tests"].values())]
        if not successful:
            continue
        best = max(successful, key=lambda item: item["context"])
        context = int(best["context"])
        response_reserve = max(2048, context // 8)
        input_tokens = max(512, context - response_reserve)
        max_input_chars = max(3500, int(input_tokens * 2.2))
        calibration[model_key] = {
            "contextWindow": context,
            "maxInputChars": max_input_chars,
            "structuredEditChars": max(3500, int(max_input_chars * 0.82)),
            "measuredAt": measured_at,
        }
    return calibration


def load_existing_calibration(path: Path):
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--contexts", nargs="+", type=int, default=list(CONTEXTS))
    parser.add_argument("--skip-structured", action="store_true")
    parser.add_argument("--stop-after-first-success", action="store_true")
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
            tests = item.get("tests") if isinstance(item.get("tests"), dict) else {}
            if args.stop_after_first_success and item.get("startup_ok") and tests and all(test.get("ok") for test in tests.values()):
                break
    logs_dir = ROOT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "model-context-bench.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (logs_dir / "model-context-summary.md").write_text(build_summary(results, selected_models=selected_models), encoding="utf-8")
    data_dir = ROOT_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    calibration_path = data_dir / "model-context-calibration.json"
    calibration = load_existing_calibration(calibration_path)
    calibration.update(build_calibration(results, selected_models=selected_models))
    calibration_path.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
