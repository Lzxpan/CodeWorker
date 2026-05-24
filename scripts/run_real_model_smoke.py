import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEBUI_DIR = ROOT / "webui"
sys.path.insert(0, str(WEBUI_DIR))

import server  # noqa: E402


def model_is_installed(model_key: str) -> bool:
    model_dir = server.get_model_directory(model_key)
    config = server.get_registry_model_config(ROOT, model_key)
    patterns = config.file_patterns if config else [server.get_model_file_pattern(model_key)]
    primary = server.match_first_model_file(model_dir, patterns)
    if primary is None:
        return False
    if config and config.mmproj_patterns:
        return server.match_first_model_file(model_dir, config.mmproj_patterns) is not None
    return True


def reclaim_other_model_ports(current_key: str) -> None:
    for key in sorted(server.SUPPORTED_MODEL_KEYS):
        if key == current_key:
            continue
        server.try_reclaim_codeworker_port(server.get_model_port(key), model_alias=server.get_model_alias(key))


def smoke_model(model_key: str, timeout_seconds: int, keep_running: bool) -> dict:
    started = time.time()
    result = {
        "modelKey": model_key,
        "displayName": server.get_model_manifest(model_key).get("displayName", model_key),
        "installed": model_is_installed(model_key),
        "status": "not-run",
        "realRun": False,
        "startupSeconds": 0,
        "replySeconds": 0,
        "reply": "",
        "error": "",
    }
    if not result["installed"]:
        result["status"] = "skipped-not-installed"
        return result
    try:
        reclaim_other_model_ports(model_key)
        ensure_result = server.ensure_local_model_server(model_key, port=server.get_model_port(model_key))
        result["startupSeconds"] = round(time.time() - started, 3)
        alias = str(ensure_result.get("modelAlias") or server.get_model_alias(model_key))
        reply_started = time.time()
        reply = server.call_local_model(
            alias,
            [{"role": "user", "content": "Reply with exactly this visible text: OK"}],
            timeout_seconds=timeout_seconds,
            max_tokens=64,
            raw_mode=True,
        )
        result["replySeconds"] = round(time.time() - reply_started, 3)
        result["reply"] = str(reply).strip()
        result["realRun"] = True
        result["status"] = "passed" if result["reply"] == "OK" else "failed-unexpected-reply"
    except Exception as exc:
        result["startupSeconds"] = round(time.time() - started, 3)
        result["status"] = "failed"
        result["error"] = str(exc)[-4000:]
    finally:
        if not keep_running:
            server.try_reclaim_codeworker_port(server.get_model_port(model_key), model_alias=server.get_model_alias(model_key))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real local-model smoke tests. No mocks or simulation are used.")
    parser.add_argument("--models", nargs="*", default=[], help="Model keys to test. Defaults to all enabled catalog models.")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-running", action="store_true")
    args = parser.parse_args()

    model_keys = [server.normalize_supported_model_key(item, "") for item in args.models]
    model_keys = [item for item in model_keys if item] or sorted(server.SUPPORTED_MODEL_KEYS)
    results = [smoke_model(key, args.timeout, args.keep_running) for key in model_keys]
    payload = {
        "kind": "real-model-smoke",
        "simulated": False,
        "models": results,
        "passed": [item["modelKey"] for item in results if item["status"] == "passed"],
        "failed": [item["modelKey"] for item in results if str(item["status"]).startswith("failed")],
        "skipped": [item["modelKey"] for item in results if str(item["status"]).startswith("skipped")],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
