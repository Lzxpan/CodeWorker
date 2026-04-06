import argparse
import os
import subprocess
import sys
from pathlib import Path


DETACHED_FLAGS = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--context", default="8192")
    parser.add_argument("--threads", default=str(os.cpu_count() or 4))
    parser.add_argument("--log", required=True)
    parser.add_argument("--err", required=True)
    args = parser.parse_args()

    server_path = Path(args.server)
    model_path = Path(args.model)
    log_path = Path(args.log)
    err_path = Path(args.err)

    if not server_path.exists():
        print(f"Server executable not found: {server_path}", file=sys.stderr)
        return 1
    if not model_path.exists():
        print(f"Model file not found: {model_path}", file=sys.stderr)
        return 1

    log_path.parent.mkdir(parents=True, exist_ok=True)
    err_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "ab") as stdout_handle, open(err_path, "ab") as stderr_handle:
        process = subprocess.Popen(
            [
                str(server_path),
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--alias",
                args.alias,
                "-m",
                str(model_path),
                "-c",
                str(args.context),
                "--threads",
                str(args.threads),
                "--n-gpu-layers",
                "0",
            ],
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=DETACHED_FLAGS,
            close_fds=True,
        )

    print(process.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
