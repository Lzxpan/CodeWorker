#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def find_codeworker_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "webui" / "rag" / "index.py").exists():
            return candidate
    default_root = Path(r"C:\Users\Admin\Desktop\CodeWorker")
    if (default_root / "webui" / "rag" / "index.py").exists():
        return default_root
    return start


def default_codeworker_root() -> Path:
    return find_codeworker_root(Path.cwd().resolve())


def main() -> int:
    parser = argparse.ArgumentParser(description="Query CodeWorker's local RAG and code graph index.")
    parser.add_argument("--codeworker-root", default=str(default_codeworker_root()))
    parser.add_argument("--project", required=True, help="Project root to index or query.")
    parser.add_argument("--data-dir", default="", help="CodeWorker data directory. Defaults to <codeworker-root>/data.")
    parser.add_argument("--query", default="", help="Symbol, file, or task query.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the project index before querying.")
    parser.add_argument("--status", action="store_true", help="Print graph status.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown context.")
    args = parser.parse_args()

    codeworker_root = Path(args.codeworker_root).resolve()
    project_root = Path(args.project).resolve()
    data_dir = Path(args.data_dir).resolve() if args.data_dir else codeworker_root / "data"
    sys.path.insert(0, str(codeworker_root / "webui"))

    from rag.index import build_code_graph_context, code_graph_status, rebuild_index, search_code_graph

    payload = {
        "project": str(project_root),
        "dataDir": str(data_dir),
        "codeworkerRoot": str(codeworker_root),
        "rebuilt": None,
        "status": None,
        "search": None,
        "context": "",
        "coverage": None,
    }

    if args.rebuild:
        payload["rebuilt"] = rebuild_index(project_root, data_dir)

    if args.status or not args.query:
        payload["status"] = code_graph_status(project_root, data_dir)

    if args.query:
        payload["search"] = search_code_graph(project_root, data_dir, args.query, limit=args.limit)
        context, coverage = build_code_graph_context(project_root, data_dir, args.query, limit=args.limit)
        payload["context"] = context
        payload["coverage"] = coverage

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if payload["rebuilt"] is not None:
        rebuilt = payload["rebuilt"]
        print(f"Rebuilt index: files={rebuilt.get('files')} chunks={rebuilt.get('chunks')} codeGraph={rebuilt.get('codeGraph')}")
    if payload["status"] is not None:
        print("Code graph status:")
        print(json.dumps(payload["status"], ensure_ascii=False, indent=2))
    if args.query:
        if payload["context"]:
            print(payload["context"])
        else:
            print("No code graph context found. Rebuild the index or fall back to rg.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
