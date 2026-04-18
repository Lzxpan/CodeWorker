import ast
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    "dist", "build", "target", "out", ".idea", ".vscode", ".next", ".nuxt", ".cache", "coverage",
    ".tmp", ".codex-artifacts", "runtime", "models", "downloads",
}
TEXT_EXTENSIONS = {
    ".pas", ".dfm", ".dpr", ".dproj", ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".java", ".kt", ".py",
    ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".rust", ".swift", ".lua", ".sql", ".sh", ".bat",
    ".cmd", ".ps1", ".cs", ".html", ".css", ".scss", ".vue", ".svelte", ".json",
    ".yaml", ".yml", ".xml", ".toml", ".ini", ".csv", ".env", ".txt", ".md", ".tex", ".rtf",
}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".gif", ".ico"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".aac", ".flac", ".m4a", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv"}
INDEXABLE_EXTENSIONS = TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
LANGUAGE_BY_EXTENSION = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".go": "Go", ".rs": "Rust", ".cs": "C#", ".cpp": "C++", ".c": "C", ".h": "C/C++ Header",
    ".hpp": "C/C++ Header", ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".json": "JSON",
    ".yaml": "YAML", ".yml": "YAML", ".xml": "XML", ".toml": "TOML", ".ini": "INI",
    ".sh": "Shell", ".bat": "Batch", ".cmd": "Batch", ".ps1": "PowerShell",
    ".md": "Markdown", ".txt": "Text", ".pdf": "PDF", ".doc": "Word", ".docx": "Word",
    ".png": "Image", ".jpg": "Image", ".jpeg": "Image", ".webp": "Image", ".mp3": "Audio",
    ".wav": "Audio", ".mp4": "Video", ".mov": "Video", ".webm": "Video",
}
GENERATED_PATH_PREFIXES = {
    ("data", "indexes"),
    ("logs",),
}
CODE_LOCATION_HINTS = (
    "在哪", "哪個檔案", "哪一段", "哪裡", "位置", "第幾行", "line", "section",
    "code", "程式碼", "函式", "function", "class", "方法",
)
MODEL_LOAD_HINTS = (
    "model", "模型", "加載", "載入", "加载", "load", "loading", "啟動", "启动",
    "llama", "gguf", "mmproj",
)
MODEL_LOAD_EXPANSIONS = {
    "ensure_runtime_and_model",
    "ensure_local_model_server",
    "launch_llama_server",
    "llama-server",
    "MODEL_FILE",
    "MODEL_MMPROJ",
    "model_file",
    "model_alias",
    "--model",
    "--mmproj",
    "resolve_model_env",
    "start-server",
    "bootstrap.manifest",
    "get_model_config",
    "MODEL_PORTS",
}
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".cs", ".cpp", ".cc", ".cxx",
    ".c", ".h", ".hpp", ".swift", ".lua", ".sql", ".sh", ".bat", ".cmd", ".ps1", ".html", ".css",
    ".scss", ".vue", ".svelte",
}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".env", ".xml"}


def project_hash(project_root: Path) -> str:
    return hashlib.sha1(str(project_root.resolve()).encode("utf-8", errors="replace")).hexdigest()[:16]


def index_dir(data_dir: Path, project_root: Path) -> Path:
    return data_dir / "indexes" / project_hash(project_root)


def should_ignore_path(project_root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return False
    parts = tuple(part.lower() for part in relative.parts)
    if not parts:
        return False
    if any(part in IGNORED_DIRS for part in parts):
        return True
    return any(parts[: len(prefix)] == prefix for prefix in GENERATED_PATH_PREFIXES)


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    return "text"


def file_language(path: Path) -> str:
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "Other")


def iter_text_files(project_root: Path, max_files: int = 5000) -> Iterable[Path]:
    count = 0
    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)
        dirs[:] = [
            item for item in dirs
            if not should_ignore_path(project_root, root_path / item)
        ]
        for filename in files:
            path = Path(root) / filename
            if should_ignore_path(project_root, path):
                continue
            suffix = path.suffix.lower()
            if suffix not in INDEXABLE_EXTENSIONS:
                continue
            try:
                size = path.stat().st_size
                if suffix in TEXT_EXTENSIONS and size > 1_500_000:
                    continue
                if suffix not in TEXT_EXTENSIONS and size > 25 * 1024 * 1024:
                    continue
            except OSError:
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_indexable_content_with_status(path: Path) -> Tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return read_text(path), "text-extracted"
    if suffix == ".pdf":
        parser_errors: List[str] = []
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages[:20]).strip()
            if text:
                return text, "text-extracted"
        except Exception as exc:
            parser_errors.append(f"pypdf: {exc}")
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(str(path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages[:20]).strip()
            if text:
                return text, "text-extracted"
        except Exception as exc:
            parser_errors.append(f"pdfplumber: {exc}")
        return f"[PDF metadata only] name={path.name} parser={' | '.join(parser_errors) if parser_errors else 'no text extracted'}", "metadata-only"
    if suffix == ".docx":
        try:
            import docx  # type: ignore
            document = docx.Document(str(path))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
            if text:
                return text, "text-extracted"
        except Exception as exc:
            return f"[DOCX metadata only] name={path.name} parser={exc}", "metadata-only"
        return f"[DOCX metadata only] name={path.name} no text extracted", "metadata-only"
    if suffix == ".doc":
        return f"[Legacy DOC metadata only] name={path.name} binary .doc extraction is not enabled", "metadata-only"
    kind = file_kind(path)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return f"[{kind} metadata only] name={path.name} extension={suffix} sizeBytes={size}", "metadata-only"


def read_indexable_content(path: Path) -> str:
    return read_indexable_content_with_status(path)[0]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_python_symbols(content: str) -> List[str]:
    symbols: List[str] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return symbols
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(f"{node.__class__.__name__}:{node.name}:{node.lineno}")
    return symbols


def extract_generic_symbols(content: str) -> List[str]:
    patterns = [
        r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)\s*\(",
        r"^\s*(?:export\s+)?class\s+([A-Za-z_][\w]*)\b",
        r"^\s*(?:public|private|protected|internal)?\s*(?:static\s+)?(?:class|interface|struct)\s+([A-Za-z_][\w]*)\b",
        r"^\s*(?:def|func|fn)\s+([A-Za-z_][\w]*)\s*\(",
    ]
    symbols: List[str] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                symbols.append(f"Symbol:{match.group(1)}:{line_no}")
                break
    return symbols


def extract_imports(content: str) -> List[str]:
    imports: List[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ", "using ", "#include")):
            imports.append(stripped[:240])
    return imports[:80]


def summarize(content: str, max_chars: int = 900) -> str:
    compact = "\n".join(line.rstrip() for line in content.splitlines() if line.strip())
    return compact[:max_chars]


def chunk_text(content: str, chunk_size: int = 2200, overlap: int = 220) -> List[str]:
    chunks: List[str] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + chunk_size)
        chunks.append(content[start:end])
        if end >= len(content):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_text_with_lines(content: str, chunk_size: int = 2200, overlap: int = 220) -> List[Dict[str, object]]:
    chunks: List[Dict[str, object]] = []
    start = 0
    line_starts = [0]
    for match in re.finditer(r"\n", content):
        line_starts.append(match.end())

    def line_for_index(index: int) -> int:
        line = 1
        for position in line_starts:
            if position > index:
                break
            line += 1
        return max(1, line - 1)

    while start < len(content):
        end = min(len(content), start + chunk_size)
        chunk = content[start:end]
        chunks.append(
            {
                "content": chunk,
                "lineStart": line_for_index(start),
                "lineEnd": line_for_index(max(start, end - 1)),
            }
        )
        if end >= len(content):
            break
        start = max(end - overlap, start + 1)
    return chunks


def ensure_column(conn: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if name not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def connect_index(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, size INTEGER, mtime REAL, sha256 TEXT, symbols TEXT, imports TEXT, summary TEXT, kind TEXT, language TEXT, extraction_status TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT, chunk_index INTEGER, content TEXT, line_start INTEGER, line_end INTEGER, kind TEXT)")
    ensure_column(conn, "files", "kind", "TEXT")
    ensure_column(conn, "files", "language", "TEXT")
    ensure_column(conn, "files", "extraction_status", "TEXT")
    ensure_column(conn, "chunks", "line_start", "INTEGER")
    ensure_column(conn, "chunks", "line_end", "INTEGER")
    ensure_column(conn, "chunks", "kind", "TEXT")
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(path, content)")
    except sqlite3.OperationalError:
        pass
    return conn


def rebuild_index(project_root: Path, data_dir: Path) -> Dict[str, object]:
    target_dir = index_dir(data_dir, project_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    db_path = target_dir / "index.sqlite"
    conn = connect_index(db_path)
    conn.execute("DELETE FROM files")
    conn.execute("DELETE FROM chunks")
    try:
        conn.execute("DELETE FROM chunks_fts")
    except sqlite3.OperationalError:
        pass

    indexed_files = 0
    indexed_chunks = 0
    skeleton: List[Dict[str, object]] = []
    manifest_files: List[Dict[str, object]] = []
    for path in iter_text_files(project_root):
        relative = path.relative_to(project_root).as_posix()
        try:
            stat = path.stat()
            content, extraction_status = read_indexable_content_with_status(path)
            digest = file_sha256(path)
        except OSError:
            continue
        kind = file_kind(path)
        language = file_language(path)
        symbols = extract_python_symbols(content) if path.suffix.lower() == ".py" else extract_generic_symbols(content)
        imports = extract_imports(content)
        summary = summarize(content)
        conn.execute(
            "INSERT OR REPLACE INTO files(path, size, mtime, sha256, symbols, imports, summary, kind, language, extraction_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                relative,
                stat.st_size,
                stat.st_mtime,
                digest,
                json.dumps(symbols, ensure_ascii=False),
                json.dumps(imports, ensure_ascii=False),
                summary,
                kind,
                language,
                extraction_status,
            ),
        )
        for idx, chunk in enumerate(chunk_text_with_lines(content)):
            chunk_content = str(chunk.get("content", ""))
            line_start = int(chunk.get("lineStart", 1) or 1)
            line_end = int(chunk.get("lineEnd", line_start) or line_start)
            cursor = conn.execute(
                "INSERT INTO chunks(path, chunk_index, content, line_start, line_end, kind) VALUES (?, ?, ?, ?, ?, ?)",
                (relative, idx, chunk_content, line_start, line_end, kind),
            )
            try:
                conn.execute("INSERT INTO chunks_fts(rowid, path, content) VALUES (?, ?, ?)", (cursor.lastrowid, relative, chunk_content))
            except sqlite3.OperationalError:
                pass
            indexed_chunks += 1
        file_record = {
            "path": relative,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "sha256": digest,
            "kind": kind,
            "language": language,
            "extractionStatus": extraction_status,
            "symbols": symbols[:20],
            "imports": imports[:20],
            "summary": summary,
        }
        skeleton.append(file_record)
        manifest_files.append({key: file_record[key] for key in ("path", "size", "mtime", "sha256", "kind", "language", "extractionStatus")})
        indexed_files += 1
    conn.commit()
    (target_dir / "skeleton.json").write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "projectHash": project_hash(project_root),
        "projectRoot": str(project_root.resolve()),
        "files": manifest_files,
        "fileCount": indexed_files,
        "chunkCount": indexed_chunks,
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()
    return {
        "projectHash": project_hash(project_root),
        "indexDir": str(target_dir),
        "database": str(db_path),
        "files": indexed_files,
        "chunks": indexed_chunks,
    }


def normalize_fts_query(query: str) -> str:
    tokens = re.findall(r"[\w.\-/]+", query, flags=re.UNICODE)
    tokens = [token.replace('"', "").strip() for token in tokens if len(token.strip()) >= 2]
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens[:12])


def query_tokens(query: str) -> List[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z_][\w.\-/]*|\d+", query, flags=re.UNICODE)
        if len(token.strip()) >= 2
    ]
    return list(dict.fromkeys(tokens))


def is_code_location_query(query: str) -> bool:
    lowered = query.lower()
    return any(hint.lower() in lowered for hint in CODE_LOCATION_HINTS)


def is_model_loading_query(query: str) -> bool:
    lowered = query.lower()
    return any(hint.lower() in lowered for hint in MODEL_LOAD_HINTS)


def expand_query_terms(query: str) -> List[str]:
    terms = query_tokens(query)
    lowered = query.lower()
    if is_model_loading_query(query):
        terms.extend(term.lower() for term in MODEL_LOAD_EXPANSIONS)
    if "開啟專案" in lowered or "open project" in lowered:
        terms.extend(["open_project", "handle_open_project", "collect_project_files", "analyze"])
    if "rag" in lowered or "檢索" in lowered or "搜尋" in lowered:
        terms.extend(["build_project_rag_context", "search_index", "rebuild_index", "rag"])
    return list(dict.fromkeys(term for term in terms if len(term) >= 2))


def path_rank_bonus(path: str, query: str) -> float:
    lowered_path = path.lower()
    suffix = Path(path).suffix.lower()
    score = 0.0
    if suffix in CODE_EXTENSIONS:
        score += 0.45
    elif suffix in CONFIG_EXTENSIONS:
        score += 0.18
    elif suffix in {".md", ".txt", ".rtf", ".tex"}:
        score -= 0.12
    if should_ignore_path(Path("."), Path(path)):
        score -= 2.0
    if is_model_loading_query(query):
        if lowered_path in {"webui/server.py", "scripts/launch_llama_server.py", "scripts/start-server.cmd", "scripts/resolve_model_env.py"}:
            score += 0.75
        if lowered_path.startswith(("docs/", "data/", "logs/")):
            score -= 0.45
    return score


def content_rank_bonus(path: str, content: str, query: str, source: str) -> float:
    lowered_content = content.lower()
    terms = expand_query_terms(query)
    score = path_rank_bonus(path, query)
    if source == "file-metadata":
        score -= 0.35 if is_code_location_query(query) else 0.05
    elif source == "fts":
        score += 0.18
    for term in terms[:24]:
        term_lower = term.lower()
        if term_lower in path.lower():
            score += 0.18
        if term_lower in lowered_content:
            score += min(lowered_content.count(term_lower), 4) * 0.08
    if is_code_location_query(query) and re.search(r"\b(def|class|function|async function|subprocess|Popen|llama-server|--model)\b", content):
        score += 0.35
    return score


def row_to_match(row: Tuple[object, ...], source: str, score: float) -> Dict[str, object]:
    path, chunk_index, content, line_start, line_end, kind = row
    return {
        "path": str(path),
        "chunkIndex": int(chunk_index or 0),
        "lineStart": int(line_start or 1),
        "lineEnd": int(line_end or line_start or 1),
        "content": str(content or "")[:1800],
        "kind": str(kind or "text"),
        "source": source,
        "score": score,
    }


def search_index(project_root: Path, data_dir: Path, query: str, limit: int = 8) -> Dict[str, object]:
    db_path = index_dir(data_dir, project_root) / "index.sqlite"
    if not db_path.exists():
        return {"ready": False, "matches": []}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    matches: List[Dict[str, object]] = []
    seen = set()
    fetch_limit = max(limit * 8, 40)
    max_candidates = max(limit * 12, 80)
    expanded_terms = expand_query_terms(query)
    expanded_query = " ".join([query, *expanded_terms])

    def add_rows(rows: Iterable[sqlite3.Row], source: str, score: float) -> None:
        for row in rows:
            key = (row["path"], row["chunk_index"])
            if key in seen:
                continue
            seen.add(key)
            content = str(row["content"] or "")
            path = str(row["path"])
            ranked_score = score + content_rank_bonus(path, content, query, source)
            matches.append(
                {
                    "path": path,
                    "chunkIndex": int(row["chunk_index"] or 0),
                    "lineStart": int(row["line_start"] or 1),
                    "lineEnd": int(row["line_end"] or row["line_start"] or 1),
                    "content": content[:1800],
                    "kind": str(row["kind"] or "text"),
                    "source": source,
                    "score": round(ranked_score, 4),
                }
            )
            if len(matches) >= max_candidates:
                return

    fts_query = normalize_fts_query(expanded_query)
    if fts_query:
        try:
            rows = conn.execute(
                """
                SELECT c.path, c.chunk_index, c.content, c.line_start, c.line_end, c.kind
                FROM chunks_fts
                JOIN chunks c ON c.rowid = chunks_fts.rowid
                WHERE chunks_fts MATCH ?
                LIMIT ?
                """,
                (fts_query, fetch_limit),
            ).fetchall()
            add_rows(rows, "fts", 1.0)
        except sqlite3.OperationalError:
            pass

    like_terms = expanded_terms[:20] or [query.lower()]
    for token in like_terms:
        if len(matches) >= max_candidates:
            break
        like = f"%{token}%"
        rows = conn.execute(
            """
            SELECT path, chunk_index, content, line_start, line_end, kind
            FROM chunks
            WHERE lower(path) LIKE ? OR lower(content) LIKE ?
            LIMIT ?
            """,
            (like, like, fetch_limit),
        ).fetchall()
        add_rows(rows, "like", 0.7)

    for token in like_terms:
        if len(matches) >= max_candidates:
            break
        like = f"%{token}%"
        rows = conn.execute(
            """
            SELECT f.path, 0 AS chunk_index, f.summary AS content, 1 AS line_start, 1 AS line_end, f.kind AS kind
            FROM files f
            WHERE lower(f.path) LIKE ?
               OR lower(f.summary) LIKE ?
               OR lower(f.symbols) LIKE ?
               OR lower(f.imports) LIKE ?
            LIMIT ?
            """,
            (like, like, like, like, fetch_limit),
        ).fetchall()
        add_rows(rows, "file-metadata", 0.5)

    conn.close()
    matches.sort(key=lambda item: (-float(item.get("score", 0) or 0), str(item.get("path", "")), int(item.get("chunkIndex", 0) or 0)))
    return {"ready": True, "matches": matches[:limit]}


def index_is_stale(project_root: Path, data_dir: Path) -> bool:
    target_dir = index_dir(data_dir, project_root)
    manifest_path = target_dir / "manifest.json"
    db_path = target_dir / "index.sqlite"
    if not manifest_path.exists() or not db_path.exists():
        return True
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return True
    indexed = {
        str(item.get("path")): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("path")
    }
    current_paths = set()
    for path in iter_text_files(project_root):
        relative = path.relative_to(project_root).as_posix()
        current_paths.add(relative)
        cached = indexed.get(relative)
        if not cached:
            return True
        try:
            stat = path.stat()
        except OSError:
            return True
        if int(cached.get("size", -1)) != int(stat.st_size):
            return True
        cached_mtime = float(cached.get("mtime", 0) or 0)
        if abs(cached_mtime - float(stat.st_mtime)) > 0.001:
            return True
        if str(cached.get("sha256", "")) != file_sha256(path):
            return True
    return set(indexed.keys()) != current_paths


def impact_analysis(project_root: Path, data_dir: Path, paths: Optional[List[str]] = None) -> Dict[str, object]:
    db_path = index_dir(data_dir, project_root) / "index.sqlite"
    if not db_path.exists():
        return {"ready": False, "impacted": []}
    conn = sqlite3.connect(str(db_path))
    selected = set(paths or [])
    rows = conn.execute("SELECT path, symbols, imports FROM files").fetchall()
    impacted = []
    for path, symbols_json, imports_json in rows:
        symbols = json.loads(symbols_json or "[]")
        imports = json.loads(imports_json or "[]")
        if not selected or path in selected or any(target in " ".join(imports) for target in selected):
            impacted.append({"path": path, "symbols": symbols[:20], "imports": imports[:20]})
    conn.close()
    return {"ready": True, "impacted": impacted[:50]}
