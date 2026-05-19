# CodeGraph Principles Applied In CodeWorker

Source studied: `colbymchenry/codegraph` at commit `c811237db865233e479a3d84e43b9f46356aefbc`.

Upstream attribution:

- Project: `colbymchenry/codegraph`
- Author / copyright holder: Colby Mchenry
- Source: https://github.com/colbymchenry/codegraph
- License: MIT License
- Notice: `MIT License Copyright (c) 2026 Colby Mchenry`

CodeGraph's useful pattern is:

1. Parse source into symbol nodes.
2. Persist nodes and relationship edges in SQLite.
3. Add FTS search over symbol names, qualified names, signatures, and docs.
4. Resolve imports/calls/extends after all files are indexed.
5. Build compact task context from entry points plus graph neighborhoods.
6. Use the graph first, then read only targeted source files.

CodeWorker implements a lightweight Python-native version:

- `webui/rag/code_graph.py` writes `code_nodes`, `code_edges`, and `code_unresolved_refs`.
- Python files use `ast` for classes, functions, methods, imports, calls, and inheritance.
- Other code files use conservative regex extraction for common class/function/method/import shapes.
- Existing RAG chunks still provide source excerpts; graph context is used as a navigation and impact layer.

Limitations:

- This is not a full tree-sitter port.
- Relationship resolution is best-effort for dynamic calls and framework magic.
- Always read target source before editing.
