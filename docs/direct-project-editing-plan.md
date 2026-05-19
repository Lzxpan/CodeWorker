# CodeWorker 本地模型直接修改專案檔案功能落地規劃

目標是讓 CodeWorker 接近 Codex 的本地修改流程：使用者提出需求，本地 LLM 產生檔案操作計畫，UI 顯示 diff / action card，使用者確認後才執行新增、修改、刪除、rename 或 command。所有修改前後都要透過 Git 建立可追蹤的 checkpoint，讓使用者能比較修改差異，發生錯誤時能復原。

## 既有基礎

- `scripts/attach-project.cmd` 已會初始化 Git repository，若沒有 commit，會建立 `Initial snapshot before aider session`。
- `/api/edit/plan` 已能產生 `pending_edit` 與 diff 建議。
- `webui/agent/runtime.py` 已有 `write_file` / `run_command` pending action 雛形。

## 目前缺口

- 尚未有正式 `/api/edit/apply` 套用修改計畫。
- 尚未有完整 `patch_file/delete_file/rename_file` action schema。
- 尚未有 Git checkpoint / diff / restore 的 WebUI 工作流。
- `generateEditPlan()` 尚未成為明確、可見、可完成套用的 UI 流程。

## 工作步驟

1. 建立 Git helper：`git_status`、`git_diff`、`create_git_checkpoint`、`restore_git_checkpoint`、`list_recent_checkpoints`。
2. 定義 pending action schema：`create_file`、`patch_file`、`replace_file`、`delete_file`、`rename_file`、`run_command`。
3. 將現有精準 search/replace edit plan 轉成 `patch_file` pending action。
4. 新增 `/api/edit/apply`，套用前建立 pre-edit checkpoint，套用後建立 post-edit checkpoint。
5. 新增 `/api/git/diff`、`/api/git/checkpoint`、`/api/git/restore`。
6. 在 UI 新增 `產生修改計畫`、`確認套用`、`查看 Git diff`、`建立 checkpoint`、`復原這次修改`。
7. 將 action result 寫入 transcript，但不要放進 LLM history。
8. 補 regression 與 Browser E2E，完整驗證三輪修改、diff、restore。
9. 更新 README / README.zh-TW / README.en 與版本歷程。
10. 合併前執行完整測試與 code review。

## 安全原則

- 所有寫入、刪除、rename、command 都必須人工確認。
- 所有 path 必須限制在 project root 內。
- 禁止修改 `.git/`、`runtime/`、`models/`、`data/indexes/`。
- `restore` 只允許回到 CodeWorker 建立的 pre-edit checkpoint。
- 若 working tree 已 dirty，pre-edit checkpoint 會包含既有變更，UI 必須提示。

## 驗證標準

- 使用者可按 `產生修改計畫`，取得可審查的檔案操作清單。
- 套用前一定有 Git pre-edit checkpoint；套用後若有檔案變更才建立 Git post-edit checkpoint，沒有檔案變更時保留完整 diff/status。
- UI 可查看修改前後 diff。
- 發生錯誤時可按 `復原這次修改` 回到 pre-edit checkpoint。
- path traversal、保護目錄、stale diff、重複 search match 都會被拒絕。
