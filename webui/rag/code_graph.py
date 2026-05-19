import ast
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Optional, Tuple


CODE_GRAPH_SCHEMA_VERSION = 1
CODE_GRAPH_CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".cs",
    ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".swift", ".php", ".rb",
    ".scala", ".dart", ".vue", ".svelte", ".html", ".css", ".scss", ".sql",
    ".sh", ".bat", ".cmd", ".ps1",
}
CALL_IGNORE_NAMES = {
    "if", "for", "while", "switch", "catch", "return", "sizeof", "typeof",
    "function", "class", "def", "new", "print", "len", "range", "str", "int",
    "float", "list", "dict", "set", "tuple", "console.log", "super",
}
IMPORT_EXTENSIONS = [
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs", ".cs",
    ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".swift", ".php", ".rb",
    ".vue", ".svelte",
]


@dataclass
class GraphNode:
    id: str
    kind: str
    name: str
    qualified_name: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str
    metadata: Dict[str, object]
    line: int


@dataclass
class UnresolvedReference:
    source: str
    reference_name: str
    reference_kind: str
    file_path: str
    line: int


def stable_id(*parts: object) -> str:
    raw = "::".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def ensure_code_graph_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS project_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS code_nodes (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            qualified_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            language TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            signature TEXT,
            docstring TEXT,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS code_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            kind TEXT NOT NULL,
            metadata TEXT,
            line INTEGER,
            UNIQUE(source, target, kind, line)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS code_unresolved_refs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            reference_name TEXT NOT NULL,
            reference_kind TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code_nodes_name ON code_nodes(name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code_nodes_file_path ON code_nodes(file_path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code_nodes_kind ON code_nodes(kind)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code_edges_source_kind ON code_edges(source, kind)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code_edges_target_kind ON code_edges(target, kind)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_code_unresolved_name ON code_unresolved_refs(reference_name)")
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS code_nodes_fts USING fts5(
                id,
                name,
                qualified_name,
                signature,
                docstring,
                content='code_nodes',
                content_rowid='rowid'
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        "INSERT OR REPLACE INTO project_metadata(key, value, updated_at) VALUES (?, ?, ?)",
        ("codeGraphSchemaVersion", str(CODE_GRAPH_SCHEMA_VERSION), int(time.time())),
    )


def reset_code_graph(conn: sqlite3.Connection) -> None:
    ensure_code_graph_schema(conn)
    conn.execute("DELETE FROM code_edges")
    conn.execute("DELETE FROM code_nodes")
    conn.execute("DELETE FROM code_unresolved_refs")
    try:
        conn.execute("DELETE FROM code_nodes_fts")
    except sqlite3.OperationalError:
        pass


def add_code_graph_file(
    conn: sqlite3.Connection,
    relative_path: str,
    suffix: str,
    language: str,
    content: str,
) -> None:
    if suffix.lower() not in CODE_GRAPH_CODE_EXTENSIONS:
        return
    nodes, edges, refs = extract_file_graph(relative_path, language, content)
    updated_at = int(time.time())
    for node in nodes:
        conn.execute(
            """
            INSERT OR REPLACE INTO code_nodes(
                id, kind, name, qualified_name, file_path, language, start_line,
                end_line, signature, docstring, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node.id, node.kind, node.name, node.qualified_name, node.file_path,
                node.language, node.start_line, node.end_line, node.signature,
                node.docstring, updated_at,
            ),
        )
        try:
            conn.execute(
                """
                INSERT INTO code_nodes_fts(rowid, id, name, qualified_name, signature, docstring)
                SELECT rowid, id, name, qualified_name, signature, docstring
                FROM code_nodes
                WHERE id = ?
                """,
                (node.id,),
            )
        except sqlite3.OperationalError:
            pass
    for edge in edges:
        insert_edge(conn, edge)
    for ref in refs:
        conn.execute(
            """
            INSERT INTO code_unresolved_refs(source, reference_name, reference_kind, file_path, line)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ref.source, ref.reference_name, ref.reference_kind, ref.file_path, ref.line),
        )


def insert_edge(conn: sqlite3.Connection, edge: GraphEdge) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO code_edges(source, target, kind, metadata, line) VALUES (?, ?, ?, ?, ?)",
        (
            edge.source,
            edge.target,
            edge.kind,
            json.dumps(edge.metadata, ensure_ascii=False, sort_keys=True),
            edge.line,
        ),
    )


def extract_file_graph(relative_path: str, language: str, content: str) -> Tuple[List[GraphNode], List[GraphEdge], List[UnresolvedReference]]:
    file_id = stable_id(relative_path, "file")
    line_count = max(1, len(content.splitlines()))
    file_node = GraphNode(
        id=file_id,
        kind="file",
        name=Path(relative_path).name,
        qualified_name=relative_path,
        file_path=relative_path,
        language=language,
        start_line=1,
        end_line=line_count,
        signature=relative_path,
    )
    if Path(relative_path).suffix.lower() == ".py":
        return extract_python_graph(relative_path, language, content, file_node)
    return extract_generic_graph(relative_path, language, content, file_node)


class PythonGraphVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str, language: str, content: str, file_node: GraphNode) -> None:
        self.relative_path = relative_path
        self.language = language
        self.content = content
        self.lines = content.splitlines()
        self.nodes: List[GraphNode] = [file_node]
        self.edges: List[GraphEdge] = []
        self.refs: List[UnresolvedReference] = []
        self.scope: List[GraphNode] = [file_node]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        graph_node = self.make_node("class", node.name, node, signature=self.signature_for_line(node.lineno), docstring=ast.get_docstring(node) or "")
        self.add_child(graph_node, node.lineno)
        for base in node.bases:
            name = dotted_name(base)
            if name:
                self.refs.append(UnresolvedReference(graph_node.id, name, "extends", self.relative_path, getattr(base, "lineno", node.lineno)))
        self.scope.append(graph_node)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        source = self.scope[0].id
        for alias in node.names:
            self.refs.append(UnresolvedReference(source, alias.name, "imports", self.relative_path, node.lineno))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        source = self.scope[0].id
        module = "." * int(node.level or 0) + (node.module or "")
        for alias in node.names:
            ref = f"{module}.{alias.name}".strip(".") if module else alias.name
            self.refs.append(UnresolvedReference(source, ref, "imports", self.relative_path, node.lineno))

    def visit_Call(self, node: ast.Call) -> None:
        current = self.current_symbol()
        name = dotted_name(node.func)
        if current and name and name not in CALL_IGNORE_NAMES:
            self.refs.append(UnresolvedReference(current.id, name, "calls", self.relative_path, getattr(node, "lineno", current.start_line)))
        self.generic_visit(node)

    def visit_function(self, node: ast.AST) -> None:
        name = getattr(node, "name", "")
        parent = self.scope[-1]
        kind = "method" if parent.kind == "class" else "function"
        graph_node = self.make_node(kind, name, node, signature=self.signature_for_line(getattr(node, "lineno", 1)), docstring=ast.get_docstring(node) or "")
        self.add_child(graph_node, getattr(node, "lineno", 1))
        self.scope.append(graph_node)
        self.generic_visit(node)
        self.scope.pop()

    def make_node(self, kind: str, name: str, node: ast.AST, signature: str = "", docstring: str = "") -> GraphNode:
        qualified = "::".join([self.relative_path, *[item.name for item in self.scope[1:]], name])
        return GraphNode(
            id=stable_id(self.relative_path, qualified, kind),
            kind=kind,
            name=name,
            qualified_name=qualified,
            file_path=self.relative_path,
            language=self.language,
            start_line=max(1, int(getattr(node, "lineno", 1) or 1)),
            end_line=max(1, int(getattr(node, "end_lineno", getattr(node, "lineno", 1)) or 1)),
            signature=signature,
            docstring=docstring[:500],
        )

    def add_child(self, graph_node: GraphNode, line: int) -> None:
        parent = self.scope[-1]
        self.nodes.append(graph_node)
        self.edges.append(GraphEdge(parent.id, graph_node.id, "contains", {}, line))

    def current_symbol(self) -> Optional[GraphNode]:
        for item in reversed(self.scope):
            if item.kind in {"function", "method"}:
                return item
        return None

    def signature_for_line(self, line: int) -> str:
        if 1 <= line <= len(self.lines):
            return self.lines[line - 1].strip()[:300]
        return ""


def extract_python_graph(relative_path: str, language: str, content: str, file_node: GraphNode) -> Tuple[List[GraphNode], List[GraphEdge], List[UnresolvedReference]]:
    visitor = PythonGraphVisitor(relative_path, language, content, file_node)
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [file_node], [], []
    visitor.visit(tree)
    return visitor.nodes, visitor.edges, visitor.refs


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    if isinstance(node, ast.Subscript):
        return dotted_name(node.value)
    return ""


def extract_generic_graph(relative_path: str, language: str, content: str, file_node: GraphNode) -> Tuple[List[GraphNode], List[GraphEdge], List[UnresolvedReference]]:
    nodes: List[GraphNode] = [file_node]
    edges: List[GraphEdge] = []
    refs: List[UnresolvedReference] = []
    lines = content.splitlines()
    symbols: List[Tuple[int, str, str, str]] = []
    patterns = [
        ("class", re.compile(r"^\s*(?:export\s+)?(?:public\s+|private\s+|protected\s+|internal\s+)?(?:abstract\s+|sealed\s+|partial\s+)?(?:class|struct|interface|trait|enum)\s+([A-Za-z_][\w]*)\b")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][\w]*)\s*\(")),
        ("function", re.compile(r"^\s*(?:def|func|fn)\s+([A-Za-z_][\w]*)\s*\(")),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][\w]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_][\w]*)\s*=>")),
        ("method", re.compile(r"^\s*(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|async\s+|override\s+|virtual\s+)*[A-Za-z_<>\[\],.?]+\s+([A-Za-z_][\w]*)\s*\([^;]*\)\s*(?:\{|=>)")),
    ]
    for line_no, line in enumerate(lines, start=1):
        for kind, pattern in patterns:
            match = pattern.search(line)
            if match and match.group(1) not in CALL_IGNORE_NAMES:
                symbols.append((line_no, kind, match.group(1), line.strip()[:300]))
                break
        import_ref = extract_import_reference(line)
        if import_ref:
            refs.append(UnresolvedReference(file_node.id, import_ref, "imports", relative_path, line_no))

    for index, (line_no, kind, name, signature) in enumerate(symbols):
        next_line = symbols[index + 1][0] - 1 if index + 1 < len(symbols) else max(line_no, len(lines))
        qualified = f"{relative_path}::{name}"
        node = GraphNode(
            id=stable_id(relative_path, qualified, kind, line_no),
            kind=kind,
            name=name,
            qualified_name=qualified,
            file_path=relative_path,
            language=language,
            start_line=line_no,
            end_line=next_line,
            signature=signature,
        )
        nodes.append(node)
        edges.append(GraphEdge(file_node.id, node.id, "contains", {}, line_no))

    for node in nodes[1:]:
        block = "\n".join(lines[node.start_line - 1: node.end_line])
        for call_match in re.finditer(r"\b([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?)\s*\(", block):
            name = call_match.group(1)
            if name == node.name or name in CALL_IGNORE_NAMES:
                continue
            line = node.start_line + block[: call_match.start()].count("\n")
            refs.append(UnresolvedReference(node.id, name, "calls", relative_path, line))
    return nodes, edges, refs


def extract_import_reference(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith(("//", "# ")):
        return ""
    quoted = re.search(r"(?:from|import|require)\s*\(?\s*['\"]([^'\"]+)['\"]", stripped)
    if quoted:
        return quoted.group(1)
    include = re.search(r"#include\s+[<\"]([^>\"]+)[>\"]", stripped)
    if include:
        return include.group(1)
    using = re.search(r"^using\s+([A-Za-z_][\w.]*)\s*;", stripped)
    if using:
        return using.group(1)
    py_from = re.search(r"^from\s+([A-Za-z_][\w.]*)\s+import\b", stripped)
    if py_from:
        return py_from.group(1)
    py_import = re.search(r"^import\s+([A-Za-z_][\w.]*)", stripped)
    if py_import:
        return py_import.group(1)
    return ""


def resolve_code_graph(conn: sqlite3.Connection) -> Dict[str, int]:
    nodes = rows_as_dicts(conn.execute("SELECT * FROM code_nodes"))
    if not nodes:
        return {"resolved": 0, "unresolved": 0, "edges": 0}
    by_name: Dict[str, List[Dict[str, object]]] = {}
    file_nodes: Dict[str, Dict[str, object]] = {}
    all_files = {str(row["file_path"]) for row in nodes if str(row["kind"]) == "file"}
    for node in nodes:
        name = str(node["name"])
        by_name.setdefault(name, []).append(node)
        if str(node["kind"]) == "file":
            file_nodes[str(node["file_path"])] = node
    refs = rows_as_dicts(conn.execute("SELECT * FROM code_unresolved_refs"))
    resolved = 0
    for ref in refs:
        source = str(ref["source"])
        reference_name = str(ref["reference_name"])
        kind = str(ref["reference_kind"])
        file_path = str(ref["file_path"])
        line = int(ref["line"] or 1)
        target: Optional[Dict[str, object]] = None
        if kind == "imports":
            import_path = resolve_import_path(reference_name, file_path, all_files)
            if import_path:
                target = file_nodes.get(import_path)
        else:
            candidates = by_name.get(reference_name) or by_name.get(reference_name.split(".")[-1]) or []
            target = choose_best_symbol(candidates, file_path)
        if not target:
            continue
        insert_edge(
            conn,
            GraphEdge(
                source=source,
                target=str(target["id"]),
                kind=kind,
                metadata={"reference": reference_name, "resolvedBy": "codeworker-light-graph"},
                line=line,
            ),
        )
        resolved += 1
    edge_count = int(conn.execute("SELECT COUNT(*) FROM code_edges").fetchone()[0] or 0)
    return {"resolved": resolved, "unresolved": max(0, len(refs) - resolved), "edges": edge_count}


def rows_as_dicts(cursor: sqlite3.Cursor) -> List[Dict[str, object]]:
    columns = [item[0] for item in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def choose_best_symbol(candidates: List[Dict[str, object]], file_path: str) -> Optional[Dict[str, object]]:
    if not candidates:
        return None
    same_file = [item for item in candidates if str(item.get("file_path", "")) == file_path]
    if same_file:
        return same_file[0]
    non_files = [item for item in candidates if str(item.get("kind", "")) != "file"]
    return (non_files or candidates)[0]


def resolve_import_path(reference_name: str, source_file: str, all_files: Iterable[str]) -> str:
    files = set(all_files)
    reference = reference_name.strip().replace("\\", "/")
    source_dir = str(PurePosixPath(source_file).parent).replace("\\", "/")
    if source_dir == ".":
        source_dir = ""
    candidates: List[str] = []
    if reference.startswith("."):
        dot_count = len(reference) - len(reference.lstrip("."))
        remainder = reference[dot_count:].replace(".", "/")
        base_parts = [] if not source_dir else source_dir.split("/")
        if dot_count > 1:
            base_parts = base_parts[: max(0, len(base_parts) - (dot_count - 1))]
        base = "/".join(part for part in ["/".join(base_parts), remainder] if part)
        candidates.extend(expand_import_candidates(base))
    elif reference.startswith("/"):
        candidates.extend(expand_import_candidates(reference.lstrip("/")))
    elif reference.startswith("./") or reference.startswith("../"):
        base = str(PurePosixPath(source_dir) / reference).replace("\\", "/")
        candidates.extend(expand_import_candidates(normalize_posix_path(base)))
    else:
        dotted = reference.replace(".", "/")
        candidates.extend(expand_import_candidates(dotted))
        candidates.extend(path for path in files if path.endswith("/" + dotted + ".py") or path == dotted + ".py")
    for candidate in candidates:
        if candidate in files:
            return candidate
    return ""


def expand_import_candidates(base: str) -> List[str]:
    base = normalize_posix_path(base)
    candidates = [base]
    candidates.extend(f"{base}{ext}" for ext in IMPORT_EXTENSIONS)
    candidates.extend(f"{base}/index{ext}" for ext in IMPORT_EXTENSIONS)
    candidates.extend(f"{base}/__init__.py")
    return list(dict.fromkeys(candidate for candidate in candidates if candidate and not candidate.startswith("../")))


def normalize_posix_path(path: str) -> str:
    parts: List[str] = []
    for part in path.replace("\\", "/").split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def code_graph_status(project_root: Path, data_dir: Path) -> Dict[str, object]:
    db_path = data_dir / "indexes" / project_hash(project_root) / "index.sqlite"
    if not db_path.exists():
        return {"ready": False, "nodeCount": 0, "edgeCount": 0, "unresolvedCount": 0, "files": 0}
    conn = sqlite3.connect(str(db_path))
    try:
        node_count = safe_count(conn, "code_nodes")
        edge_count = safe_count(conn, "code_edges")
        unresolved_count = safe_count(conn, "code_unresolved_refs")
        file_count = conn.execute("SELECT COUNT(*) FROM code_nodes WHERE kind = 'file'").fetchone()[0] if node_count else 0
    finally:
        conn.close()
    return {
        "ready": bool(node_count),
        "nodeCount": int(node_count),
        "edgeCount": int(edge_count),
        "unresolvedCount": int(unresolved_count),
        "files": int(file_count or 0),
    }


def safe_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)
    except sqlite3.OperationalError:
        return 0


def search_code_graph(project_root: Path, data_dir: Path, query: str, limit: int = 8) -> Dict[str, object]:
    db_path = data_dir / "indexes" / project_hash(project_root) / "index.sqlite"
    if not db_path.exists():
        return {"ready": False, "nodes": [], "edges": []}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if not table_exists(conn, "code_nodes") or not table_exists(conn, "code_edges"):
            return {"ready": False, "nodes": [], "edges": [], "status": code_graph_status(project_root, data_dir)}
        nodes = find_matching_nodes(conn, query, limit)
        node_ids = [str(node["id"]) for node in nodes]
        edges = related_edges(conn, node_ids, limit=max(12, limit * 3))
        status = code_graph_status(project_root, data_dir)
    finally:
        conn.close()
    return {
        "ready": bool(nodes) or bool(status.get("ready")),
        "nodes": [public_node(node) for node in nodes],
        "edges": edges,
        "status": status,
    }


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def find_matching_nodes(conn: sqlite3.Connection, query: str, limit: int) -> List[sqlite3.Row]:
    seen = set()
    rows: List[sqlite3.Row] = []
    fts_query = normalize_graph_query(query)
    if fts_query:
        try:
            for row in conn.execute(
                """
                SELECT n.*
                FROM code_nodes_fts f
                JOIN code_nodes n ON n.rowid = f.rowid
                WHERE code_nodes_fts MATCH ?
                LIMIT ?
                """,
                (fts_query, max(limit * 2, 12)),
            ).fetchall():
                if row["id"] not in seen:
                    rows.append(row)
                    seen.add(row["id"])
        except sqlite3.OperationalError:
            pass
    for token in graph_tokens(query)[:8]:
        if len(rows) >= limit:
            break
        like = f"%{token.lower()}%"
        for row in conn.execute(
            """
            SELECT *
            FROM code_nodes
            WHERE lower(name) LIKE ?
               OR lower(qualified_name) LIKE ?
               OR lower(signature) LIKE ?
               OR lower(file_path) LIKE ?
            LIMIT ?
            """,
            (like, like, like, like, max(limit * 2, 12)),
        ).fetchall():
            if row["id"] not in seen:
                rows.append(row)
                seen.add(row["id"])
            if len(rows) >= limit:
                break
    return rows[:limit]


def normalize_graph_query(query: str) -> str:
    tokens = graph_tokens(query)
    return " OR ".join(f'"{token}"' for token in tokens[:8])


def graph_tokens(query: str) -> List[str]:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z_][\w.:\-/]*|\d+|[\u4e00-\u9fff]{2,}", query)
        if len(token.strip()) >= 2
    ]
    return list(dict.fromkeys(tokens))


def related_edges(conn: sqlite3.Connection, node_ids: List[str], limit: int = 24) -> List[Dict[str, object]]:
    if not node_ids:
        return []
    placeholders = ",".join("?" for _ in node_ids)
    rows = conn.execute(
        f"""
        SELECT e.kind, e.line,
               s.name AS source_name, s.kind AS source_kind, s.file_path AS source_file, s.start_line AS source_line,
               t.name AS target_name, t.kind AS target_kind, t.file_path AS target_file, t.start_line AS target_line
        FROM code_edges e
        JOIN code_nodes s ON s.id = e.source
        JOIN code_nodes t ON t.id = e.target
        WHERE e.source IN ({placeholders}) OR e.target IN ({placeholders})
        ORDER BY e.kind, s.file_path, s.start_line
        LIMIT ?
        """,
        [*node_ids, *node_ids, limit],
    ).fetchall()
    return [
        {
            "kind": row["kind"],
            "line": int(row["line"] or 1),
            "source": {
                "name": row["source_name"],
                "kind": row["source_kind"],
                "path": row["source_file"],
                "line": row["source_line"],
            },
            "target": {
                "name": row["target_name"],
                "kind": row["target_kind"],
                "path": row["target_file"],
                "line": row["target_line"],
            },
        }
        for row in rows
    ]


def public_node(row: sqlite3.Row) -> Dict[str, object]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "qualifiedName": row["qualified_name"],
        "path": row["file_path"],
        "language": row["language"],
        "lineStart": int(row["start_line"] or 1),
        "lineEnd": int(row["end_line"] or row["start_line"] or 1),
        "signature": row["signature"] or "",
    }


def build_code_graph_context(project_root: Path, data_dir: Path, query: str, limit: int = 10) -> Tuple[str, Dict[str, object]]:
    result = search_code_graph(project_root, data_dir, query, limit=limit)
    nodes = result.get("nodes", []) if isinstance(result, dict) else []
    edges = result.get("edges", []) if isinstance(result, dict) else []
    status = result.get("status", {}) if isinstance(result, dict) else {}
    if not nodes and not edges:
        return "", {
            "ready": bool(status.get("ready")),
            "nodeCount": int(status.get("nodeCount", 0) or 0),
            "edgeCount": int(status.get("edgeCount", 0) or 0),
            "nodesSent": 0,
            "edgesSent": 0,
        }
    lines = [
        "CODE GRAPH CONTEXT",
        "CodeWorker has indexed symbol nodes and relationship edges for faster code exploration.",
        "Use this before broad file scanning: entry points identify relevant symbols, and edges show contains/imports/calls/extends relationships.",
        "",
        "ENTRY POINTS",
    ]
    for node in nodes[:limit]:
        if not isinstance(node, dict):
            continue
        location = f"{node.get('path', '')}:{node.get('lineStart', 1)}"
        signature = str(node.get("signature", "")).strip()
        lines.append(f"- {node.get('name')} ({node.get('kind')}) at {location}")
        if signature:
            lines.append(f"  signature: {signature[:220]}")
    if edges:
        lines.extend(["", "RELATIONSHIPS"])
        for edge in edges[: max(10, limit * 2)]:
            if not isinstance(edge, dict):
                continue
            source = edge.get("source", {}) if isinstance(edge.get("source"), dict) else {}
            target = edge.get("target", {}) if isinstance(edge.get("target"), dict) else {}
            lines.append(
                "- "
                f"{source.get('name')} ({source.get('path')}:{source.get('line')}) "
                f"--{edge.get('kind')}--> "
                f"{target.get('name')} ({target.get('path')}:{target.get('line')})"
            )
    return "\n".join(lines), {
        "ready": True,
        "nodeCount": int(status.get("nodeCount", 0) or 0),
        "edgeCount": int(status.get("edgeCount", 0) or 0),
        "nodesSent": len(nodes),
        "edgesSent": len(edges),
    }


def project_hash(project_root: Path) -> str:
    return hashlib.sha1(str(project_root.resolve()).encode("utf-8", errors="replace")).hexdigest()[:16]
