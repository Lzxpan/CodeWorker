# Third-Party Notices

## CodeGraph

- Project: `colbymchenry/codegraph`
- Author / copyright holder: Colby Mchenry
- Source: https://github.com/colbymchenry/codegraph
- License: MIT License
- Upstream license notice: `MIT License Copyright (c) 2026 Colby Mchenry`

CodeWorker's CodeGraph support was implemented as a lightweight Python-native graph inside `webui\rag\code_graph.py`, with a repo-local Codex plugin at `plugins\codeworker-codegraph`. The design follows CodeGraph's local-first idea of indexing symbols and relationships before broad file exploration, but it does not vendor the upstream TypeScript package.
