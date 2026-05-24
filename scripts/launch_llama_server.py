import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--mmproj")
    parser.add_argument("--context", default="8192")
    parser.add_argument("--cache-type-k")
    parser.add_argument("--cache-type-v")
    parser.add_argument("--threads", default=str(os.cpu_count() or 4))
    parser.add_argument("--n-gpu-layers", default="0")
    parser.add_argument("--n-cpu-moe")
    parser.add_argument("--batch-size")
    parser.add_argument("--ubatch-size")
    parser.add_argument("--flash-attn", action="store_true")
    parser.add_argument("--jinja", action="store_true")
    parser.add_argument("--mlock", action="store_true")
    parser.add_argument("--log", required=True)
    parser.add_argument("--err", required=True)
    args = parser.parse_args()

    server_path = Path(args.server)
    model_path = Path(args.model)
    mmproj_path = Path(args.mmproj) if args.mmproj else None
    log_path = Path(args.log)
    err_path = Path(args.err)

    if not server_path.exists():
        print(f"Server executable not found: {server_path}", file=sys.stderr)
        return 1
    if not model_path.exists():
        print(f"Model file not found: {model_path}", file=sys.stderr)
        return 1
    if mmproj_path is not None and not mmproj_path.exists():
        print(f"mmproj file not found: {mmproj_path}", file=sys.stderr)
        return 1

    log_path.parent.mkdir(parents=True, exist_ok=True)
    err_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "ab") as stdout_handle, open(err_path, "ab") as stderr_handle:
        command = [
            str(server_path),
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--alias",
            args.alias,
            "-m",
            str(model_path),
        ]
        if mmproj_path is not None:
            command.extend(["--mmproj", str(mmproj_path)])
        if args.cache_type_k:
            command.extend(["--cache-type-k", str(args.cache_type_k)])
        if args.cache_type_v:
            command.extend(["--cache-type-v", str(args.cache_type_v)])
        if args.flash_attn:
            command.extend(["--flash-attn", "on"])
        if args.jinja:
            command.append("--jinja")
        if args.mlock:
            command.append("--mlock")
        if args.n_cpu_moe:
            command.extend(["--n-cpu-moe", str(args.n_cpu_moe)])
        if args.batch_size:
            command.extend(["--batch-size", str(args.batch_size)])
        if args.ubatch_size:
            command.extend(["--ubatch-size", str(args.ubatch_size)])
        command.extend([
            "-c",
            str(args.context),
            "--threads",
            str(args.threads),
            "--parallel",
            "1",
            "--cache-ram",
            "0",
            "--no-warmup",
            "--n-gpu-layers",
            str(args.n_gpu_layers),
        ])
        launch_metadata = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "event": "llama_server_subprocess_launch",
            "python": sys.executable,
            "platform": platform.platform(),
            "server": str(server_path),
            "host": args.host,
            "port": str(args.port),
            "alias": args.alias,
            "model": str(model_path),
            "mmproj": str(mmproj_path) if mmproj_path else "",
            "context": str(args.context),
            "threads": str(args.threads),
            "nGpuLayers": str(args.n_gpu_layers),
            "nCpuMoe": str(args.n_cpu_moe or ""),
            "batchSize": str(args.batch_size or ""),
            "ubatchSize": str(args.ubatch_size or ""),
            "flashAttn": bool(args.flash_attn),
            "jinja": bool(args.jinja),
            "mlock": bool(args.mlock),
            "cacheTypeK": str(args.cache_type_k or ""),
            "cacheTypeV": str(args.cache_type_v or ""),
            "command": command,
        }
        stdout_handle.write(("[CODEWORKER_LAUNCH_METADATA] " + json.dumps(launch_metadata, ensure_ascii=False) + "\n").encode("utf-8"))
        stdout_handle.flush()
        process = subprocess.Popen(
            command,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=DETACHED_FLAGS,
            close_fds=True,
        )
        stdout_handle.write(f"[CODEWORKER_LAUNCH_PID] {process.pid}\n".encode("utf-8"))
        stdout_handle.flush()

    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
