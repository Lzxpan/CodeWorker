# CodeWorker V1.01.002

> 離線、可攜、以隱私與資安為優先的 Windows 本地 LLM 程式碼助理。

[繁體中文完整說明](README.zh-TW.md) | [English](README.en.md)

---

## 1. 功能說明

`CodeWorker` 將 `llama.cpp`、`WinPython`、`PortableGit`、GGUF 模型與 Web UI 整合在同一個 Windows 工作目錄。它適合不能上傳原始碼、不能使用雲端模型，或需要帶到客戶端、內網、air-gapped environment 的開發情境。

主要能力：

- 本機模型服務：預設使用 `Gemma 4 26B`，由 bundled `llama.cpp` service 啟動，不需要 Ollama。
- 多模型選擇：保留 `Gemma 4 26B` 與 `Qwen 3.5 9B Vision`，並新增 `Qwen3-Coder 30B A3B`、`GLM-4.6`、`Qwen2.5-Coder 14B Instruct`、`DeepSeek-Coder V2 Lite`。
- 硬體自動最佳化：Web UI 會偵測 RAM、CPU、GPU vendor、VRAM、`nvidia-smi` 與 Vulkan 可用性，推薦模型並套用 backend、context、threads 與 GPU layers。
- Context 下拉選單：每個模型可獨立選擇自己的 context options，支援 `4k` 到 `256k`，`GLM-4.6` 另支援 `200k` 選項。
- 全專案檢索：開啟專案後，即使沒有 pinned files，也會使用本機 RAG index 搜尋相關檔案、symbols、summary 與 chunks。
- CodeGraph 式語意索引：RAG 重建時會同步建立 `code_nodes`、`code_edges` 與 `code_unresolved_refs`，提供 symbol entry points、imports、calls、extends 與 impact navigation。
- 分析專案檔案結構：以 deterministic 多語言分類找出入口、核心程式、專案設定、UI、資源、測試與可忽略產物，作為釘選前的篩選工具。
- 單一訊息流：AI 回答、專案結構分析、CodeGraph 查詢、context coverage 與檔案生成確認都保存在同一個 transcript，可以在同一個區塊上下捲動回看。
- Codex plugin：新增 `plugins\codeworker-codegraph`，可安裝到 Codex 後用 skill/script 查 CodeWorker 本機 graph，再決定要讀哪些檔案。
- 聚焦上下文：在 `檔案樹` 勾選檔案時，pinned files 會優先於全專案 RAG。
- 附件分析：支援程式碼、設定、文件、圖片、音訊與影片；可抽文字、keyframes 或 transcript 時會送入模型，否則送 metadata fallback。
- 多對話串：右側 `240px` thread panel 可新增、切換、重新命名、刪除對話串，每個 thread 保留自己的 history、memory 與 transcript。
- 模型主導檔案生成：在一般對話中要求產生文件即可，模型會先產生內容與標題，CodeWorker 依模型標題自動命名並建立 pending preview；確認後才寫入 `.txt/.md/.py/.js/.ts/.json/.html/.css/.yaml/.sql/.cs/.docx/.pdf/.pptx/.xlsx`。
- Agent 安全機制：寫檔、patch、刪檔、rename 與執行 command 前都會建立 pending action，使用者確認後才執行；套用前會建立 Git checkpoint，套用後若有檔案變更會建立 post checkpoint，可查看 diff 並復原這次修改。
- 直接修改專案檔案：`產生修改計畫` 會優先產生可審查、可套用的 `patch_file`，模型只要能提供唯一命中的 `search/replace`，CodeWorker 就能轉成真正的檔案修改 action，而不是只輸出文字建議。
- 模型 patch 容錯：若本地模型回傳的 JSON 不完整，但仍能抽出 `path`、`search`、`replace`，且 `search` 在目標檔案中唯一命中，CodeWorker 會救回為可確認套用的 patch；如果無法安全定位才降級為保守文字建議。
- 套用後驗證建議：修改完成後會依專案型態建議下一步驗證指令，例如 `.sln/.csproj` 專案會提示 `dotnet build`，`package.json` 會提示 `npm test` / `npm run build`，但不會自動執行有副作用的 command。
- 版本來源與啟動驗證：版本由根目錄 `VERSION` 統一管理，`/api/status` 會回傳 `appVersion`、`appName`、`rootDir` 與 `serverPath`，`scripts\launch-webui.cmd` 會檢查實際啟動版本並用 cache-busting URL 開啟頁面。

---

## 2. 重點注意事項

- 第一次執行需要網路下載 runtime 與模型；完成後可離線使用。
- `Qwen3-Coder 30B A3B`、`GLM-4.6`、`Qwen2.5-Coder 14B Instruct`、`DeepSeek-Coder V2 Lite` 不會在第一次 bootstrap 時自動下載，需由使用者選定模型後再下載。
- `256k` context 是可選上限，不代表每台機器都能穩定跑滿；若模型啟動失敗，UI 會顯示錯誤與 log path，不會自動降級。
- 建議至少 `32GB RAM` 等級；大型 context、圖片、影片 keyframes 與長回答都會增加記憶體壓力。
- 高階模型與 GPU backend 尚需在高階硬體實機驗證；測試時請保留 `logs\hardware-optimization.jsonl` 與對應的 `logs\llama-server-<model>-*.log` / `.err.log`。
- 未開啟專案時只做一般問答；已開啟專案且未釘選檔案時使用全專案 RAG；有 pinned files 時優先使用 pinned context。
- 影片不是直接把 MP4 binary 丟給模型，而是先用 `FFmpeg` 抽 keyframes；音訊與影片音軌會嘗試 `whisper.cpp` speech-to-text。
- 檔案生成與 Agent 寫入都必須確認後才會落到 project root；生成完成後 UI 會顯示實際檔案路徑與檔名。
- `產生修改計畫` 會先建立可審查的檔案操作清單；`確認套用` 前會建立 Git checkpoint，套用後若有檔案變更會建立 post checkpoint，`查看 Git diff` 可比對變更，必要時可 `復原這次修改`。
- `產生修改計畫` 的速度不代表功能完成度。CodeWorker 的判準是：必須有可定位的檔案、可審查的 diff、可確認套用的 action，以及套用後能透過 Git diff / build / test 驗證；如果只能產生文字建議，UI 會標示為保守建議，不會假裝已能改 code。
- 對於已知且可安全判斷的局部修改，CodeWorker 可能使用本地 deterministic patch 直接產生 `patch_file`。這不是單純加速，而是先確認原始片段唯一命中，再交給相同的 pending action / Git checkpoint / restore 流程套用。
- 對於一般修改需求，CodeWorker 會要求本地模型輸出 `search/replace`。只要 `search` 在本機檔案唯一命中，且安全檢查通過，就會變成真正可套用的 `patch_file`；若命中 0 次、多次、越界、保護目錄或高風險操作未確認，都會被拒絕。
- `scripts\bootstrap.cmd` 不是 `git pull` 的替代品。更新另一台電腦時必須先拉到最新 repo，再執行 bootstrap 補 runtime / packages。新版 bootstrap 會先停止同一個 CodeWorker root/runtime 下的舊 process，避免舊 WebUI 還在 port 上繼續服務。
- 如果更新後 Web UI 仍顯示舊版，請先檢查 `/api/status` 的 `appVersion`、`rootDir`、`serverPath`，以及 `logs\webui-*.log` 開頭三行；這比只看瀏覽器畫面更可靠，因為瀏覽器可能有舊快取或捷徑可能指向另一個舊資料夾。
- CodeGraph 功能參考 `colbymchenry/codegraph` 的本機語意索引做法；出處、作者與授權資訊列於 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

---

## 3. 安裝方式

### 第一次完整準備

```cmd
scripts\bootstrap.cmd
```

這會依 `config\bootstrap.manifest.json` 準備：

- `llama.cpp`
- `WinPython`
- `PortableGit`
- `FFmpeg`
- `whisper.cpp` 與 speech-to-text model
- `Gemma 4 26B` / `Qwen 3.5 9B Vision` GGUF 與 `mmproj`
- Python 文件套件：`pypdf`、`pdfplumber`、`python-docx`、`reportlab`、`python-pptx`、`openpyxl`

### 更新現有安裝

```cmd
git pull
scripts\bootstrap.cmd
scripts\launch-webui.cmd
```

更新檢查重點：

1. Web UI 左上角應顯示 `CodeWorker V1.01.002`。
2. `scripts\bootstrap.cmd` 會補齊 runtime、Python packages、模型 manifest 與既有下載項目，不會重複下載已存在且校驗通過的檔案。
3. bootstrap 一開始會停止同一個 CodeWorker root/runtime 下的舊 process，避免舊 WebUI server 繼續佔用 port。
4. `scripts\launch-webui.cmd` 會重新啟動 `http://127.0.0.1:8764`；若 port 上已有舊的 CodeWorker Web UI，會先回收舊 process。
5. launch 會讀取根目錄 `VERSION`，並呼叫 `/api/status` 檢查實際回傳的 `appVersion` 是否符合預期；若版本不一致，啟動等待會失敗，不會讓你誤以為新版已開啟。
6. launch 開啟瀏覽器時會使用 `?v=版本-時間戳`，降低瀏覽器載入舊 `index.html` 或舊 JavaScript 快取的機率。
7. 開啟專案後可執行 `分析專案檔案結構`、`用目前輸入查 CodeGraph`、`重新掃描索引`、`產生修改計畫` 與一般聊天，結果都會出現在同一個 transcript。

### 更新後仍看到舊版本時的檢查方式

如果另一台電腦更新後仍看到 `V1.00.000` 或其他舊版，不要只看瀏覽器畫面，請依序檢查：

```cmd
git pull
type VERSION
scripts\bootstrap.cmd
scripts\launch-webui.cmd
```

然後在 PowerShell 查 `/api/status`：

```powershell
(Invoke-RestMethod -Uri "http://127.0.0.1:8764/api/status").data |
  Select-Object appVersion,appName,rootDir,serverPath |
  ConvertTo-Json
```

正確結果應類似：

```json
{
  "appVersion": "V1.01.002",
  "appName": "CodeWorker V1.01.002",
  "rootDir": "D:\\CodeWorker",
  "serverPath": "D:\\CodeWorker\\webui\\server.py"
}
```

如果 `appVersion` 是舊版，代表實際跑的 server source 還是舊的；如果 `rootDir` 或 `serverPath` 指到不同資料夾，代表你啟動的是另一份 CodeWorker。新版 `logs\webui-*.log` 開頭也會列出：

```text
CodeWorker V1.01.002 Web UI running at http://127.0.0.1:8764
RootDir: D:\CodeWorker
ServerPath: D:\CodeWorker\webui\server.py
```

log 中若只看到 `ConnectionAbortedError` / `WinError 10053`，通常只是瀏覽器或啟動探測連線中途關閉；新版已忽略這類中斷，避免它蓋過真正的版本資訊。

### 啟動 Web UI

```cmd
scripts\launch-webui.cmd
```

開啟：

```text
http://127.0.0.1:8764
```

### 選用 CLI agent

```cmd
scripts\install-aider.cmd
```

---

## 4. 使用方式與教學

### 畫面範例

![CodeWorker V1.01.002 繁中 Web UI 畫面](docs/screenshots/webui-overview-zh-v101002.png)

### 一般問答

1. 啟動 Web UI。
2. 不必開啟專案，直接在主對話框提問。
3. 此模式不會加入 `PROJECT RAG CONTEXT`、pinned files 或 file tree。

### 專案搜尋與問答

1. 在 `專案路徑` 選擇專案根目錄。
2. 點 `開啟專案`。
3. 需要先整理大量檔案時點 `分析專案檔案結構`。
4. 直接詢問「在哪個檔案」、「哪段 code」、「要怎麼修改」；沒有 pinned files 時會自動用 RAG 搜尋全專案。
5. 若要聚焦少數檔案，在 `檔案樹` 勾選檔名。

### 分析專案檔案結構與釘選

1. 開啟專案後按 `分析專案檔案結構`。
2. CodeWorker 會依不同語言與工具鏈分類入口、核心 source、project configs、UI/form、assets、tests、generated files 與 build outputs。
3. 結果會以 transcript tool card 顯示，不會覆蓋聊天紀錄。
4. 按 `一鍵釘選建議檔案` 可把入口、設定、核心程式與 UI/測試檔加入 pinned files，再讓 AI 分析或修改。

### CodeGraph 關聯查詢

CodeGraph 適合在「還不知道要釘選哪些檔案」或「修改前想確認影響範圍」時使用。

1. 在對話輸入框輸入目前專案的 symbol、class/function、檔名或問題，例如 `Form1`、`AudioManager`、`Program.cs`、`誰呼叫 build_project_rag_context？`。
2. 按 `用目前輸入查 CodeGraph`。這一步只查本機 SQLite graph，不會問 AI。
3. transcript 會顯示命中 symbols、relationships、matched files、nodes/edges/unresolved 與下一步提示。
4. 若結果符合目標，按 `釘選命中文件`，再按一般 `送出`，AI 就會用這些 pinned files 回答。
5. 若查不到新檔案或新 symbol，按 `重新掃描索引`。它會重建 RAG + CodeGraph index，完成後保留重建摘要；若輸入框仍有 query，會再追加一張查詢結果卡。

優點：

- 先找 symbol 與關聯，再決定讀哪些檔案，降低大型專案中亂翻檔案的成本。
- 可在修改前檢查 callers/callees/imports/extends，避免漏掉受影響位置。
- 全程本機 SQLite 與本機模型，不需要 API key，也不會把專案送到雲端。
- 與 `分析專案檔案結構` 搭配時，先用檔案分類縮小範圍，再用 CodeGraph 查 symbol 關聯。

### 直接修改專案檔案

CodeWorker 的目標不是只回答「你應該怎麼改」，而是能在使用者確認後真正修改專案檔案。這個流程目前分成「產生計畫」與「確認套用」兩段，目的是讓本地模型可以協助開發，同時避免失控寫檔。

操作方式：

1. 開啟專案。
2. 建議先用 `分析專案檔案結構` 或 CodeGraph 查詢找出要修改的檔案，再釘選相關檔案；小型專案也可以不釘選，讓 RAG / CodeGraph 自動找候選。
3. 在對話輸入框輸入修改需求，例如：「幫我修改按方向鍵的下不要直接掉到底，改成按 ctrl 掉到底。」
4. 按 `產生修改計畫`。
5. transcript 會顯示修改位置、命中函式 / 區塊、修改原因、before snippet、after snippet、diff 與 pending action。
6. 檢查 diff 正確後按 `確認套用`。
7. CodeWorker 會建立 pre-edit Git checkpoint，套用 `patch_file` / `create_file` / `replace_file` / `delete_file` / `rename_file` / `run_command`，若檔案有變更再建立 post-edit checkpoint。
8. 套用後可以按 `查看 Git diff` 檢查變更；若有問題可按 `復原這次修改` 回到 pre-edit checkpoint。

直接修改的安全規則：

- 所有寫入都限制在 project root 內。
- `.git/`、`runtime/`、`models/`、`data/indexes/` 等保護路徑會被拒絕。
- `patch_file` 的 `search` 片段必須在當前檔案中剛好命中 1 次；命中 0 次代表模型看的是舊內容，命中多次代表風險太高，都不會套用。
- `delete_file`、`rename_file`、`replace_file`、`run_command` 屬於高風險操作，必須明確確認。
- 套用前後使用 Git checkpoint，不另外複製整個資料夾，避免大量專案造成備份爆量。
- 如果使用者原本已有 dirty working tree，pre-edit checkpoint 會包含既有變更，UI 會顯示 Git 狀態與 diff。

模型 patch 如何落地：

- 對於一般需求，本地模型會被要求輸出 JSON 結構，內含 `path`、`target`、`reason`、`operations.search` 與 `operations.replace`。
- CodeWorker 不會直接相信模型輸出，而是讀取本機檔案，確認 `search` 唯一命中後才建立 `patch_file` action。
- 如果模型 JSON 不完整，但仍能抽出 `path`、`search`、`replace`，CodeWorker 會嘗試 salvage；只要本機驗證安全，仍可產生真正 action。
- 如果模型只輸出文字建議、片段無法定位、或引入明顯不安全內容，就會保留為 advisory，不會假裝可以套用。
- 對於少數非常明確且可驗證的情境，CodeWorker 會使用本地 deterministic patch 產生 action；這仍然走相同的 diff、確認、Git checkpoint 與 restore 流程。

套用後驗證：

- CodeWorker 會依專案檔案推斷建議驗證命令。
- `.sln` / `.csproj`：建議 `dotnet build`。
- `package.json`：建議 `npm test` 或 `npm run build`。
- `pyproject.toml` / `pytest.ini` / `tests/`：建議 `pytest`。
- `Cargo.toml`：建議 `cargo test`。
- `go.mod`：建議 `go test ./...`。
- 這些命令目前是建議，不會自動執行，因為 build/test script 可能有副作用或耗時很長。

### 實際功能修正範例

在 `C:\Games` Tetris 專案中，需求「按方向鍵的下不要直接掉到底，改成按 Ctrl 掉到底」會被產生為真正的 `patch_file`。修改後 `Form1_KeyDown` 類似：

```csharp
case Keys.Down:
case Keys.S:
    if (MovePiece(0, 1))
    {
        score += 1;
    }

    break;
case Keys.Control:
case Keys.ControlKey:
case Keys.LControlKey:
case Keys.RControlKey:
    HardDrop();
    break;
```

這代表：

- `Down`：只下降一格。
- `S`：只下降一格。
- `Ctrl` / `ControlKey` / `LControlKey` / `RControlKey`：直接掉到底。
- 舊的 `Down + Control -> HardDrop()` 區塊會被移除。
- 如果同一句需求在已完成後再次送出，CodeWorker 會回覆「目前專案已符合這次修改需求，沒有需要套用的檔案操作」，避免再丟給模型浪費時間或產生重複 patch。

### 單一訊息流與 streaming 閱讀

- 對話、工具結果、CodeGraph、專案結構分析、context coverage 與檔案確認都會存在同一個 transcript。
- AI streaming 時，只有使用者停在底部附近才會自動跟隨；如果你往上捲閱讀舊內容，畫面不會被強制拉回底部。
- 切換 thread 或重新整理頁面後，chat 與 tool cards 會從 persisted `transcript` 回放；舊 thread 若沒有 `transcript`，會從既有 `history` 自動轉成基本顯示。

### 安裝 CodeWorker CodeGraph Codex plugin

CodeWorker 也提供 repo-local Codex plugin：

```cmd
codex plugin install plugins\codeworker-codegraph
```

安裝後，在 Codex 裡可使用 `codeworker-codegraph` skill。常用查詢：

```powershell
runtime\WinPython\python\python.exe C:\Users\Admin\.codex\skills\codeworker-codegraph\scripts\query_codeworker_graph.py --project C:\path\to\project --status
runtime\WinPython\python\python.exe C:\Users\Admin\.codex\skills\codeworker-codegraph\scripts\query_codeworker_graph.py --project C:\path\to\project --rebuild --query "Form1"
runtime\WinPython\python\python.exe C:\Users\Admin\.codex\skills\codeworker-codegraph\scripts\query_codeworker_graph.py --project C:\path\to\project --query "AudioManager callers" --json
```

使用情境：

- 要修改功能前，先查相關 symbol 與呼叫關係。
- 要交接陌生專案時，先用 graph 找入口與核心檔案。
- 要讓 Codex 減少無目的 `rg` / `Read`，先用 graph 當導航圖，再讀目標檔案。

推薦問題：

- 「請問加載 model 的 code 在哪個檔案的哪一段？」
- 「想更新遊戲速度要怎麼修改？請列出檔案路徑與原因。」
- 「我加入網路連線對戰，第一步要改哪些檔案？」

### Context 設定

1. 在聊天輸入區底部的 `Context` 下拉選單選擇 `4k` 到 `256k`。
2. 每個模型會記住自己的選擇。
3. 如果現有 `llama-server` context 低於目前選擇，下一次啟動模型時會用新 context 重啟。
4. 若 `256k` 在本機失敗，請看左側錯誤區與 `logs/llama-server-*.err.log`。

### 對話串

- 右側 `對話串` 可新增、切換、重新命名與刪除 thread。
- 每個 thread 保存自己的 `history`、`memory_summary`、`modelKey` 與 `projectPath`。
- `清空對話` 只清目前 thread，不會清掉其他 thread。

### 附件分析

1. 點 `上傳檔案`，或把截圖貼到聊天輸入區。
2. 可上傳程式碼、設定檔、PDF、DOCX、圖片、音訊與影片。
3. 圖片會先嘗試 native vision；影片會先抽 keyframes；音訊會嘗試 speech-to-text。
4. 若 extractor 或 native payload 不可用，CodeWorker 會送 metadata 與限制說明，不會假裝已看見內容。

### 檔案生成

1. 開啟專案。
2. 直接用一般聊天要求模型生成檔案，例如：「我要生成一個專案功能介紹的 PPT 文件」。
3. 模型會先產生文件內容，第一行標題會作為自動命名依據；CodeWorker 會用這份回覆建立 pending preview。
4. 若要把上一則回答輸出成文件，可以直接寫：「把剛剛的說明與使用場景做成一個 PPTX 跟 PDF 檔」或「幫我把說明生成 Word 檔」。
5. 若同一則訊息已貼上完整 Markdown 內容，例如「請把上面的內容生成docx檔給我」後接 `# 標題`，CodeWorker 會直接建立 pending preview，不再呼叫模型重寫內容。
6. 若要求「把上面的內容 / 剛剛的回答 / 上一則回答」生成文件，CodeWorker 會直接取上一則 assistant 可見回答建立 preview，不再呼叫模型。
7. 若同一句話提到多個格式，CodeWorker 會建立多個 pending preview，例如 `.pptx` 與 `.pdf` 各一個。
8. Word 請寫明 `Word`、`word檔`、`docx` 或 `docx檔`，例如：「請把剛剛的回答生成word檔」。
9. 純文字與程式碼可直接寫副檔名或格式別名，例如 `txt檔`、`md檔`、`py檔`、`js檔`、`json檔`、`html檔`、`css檔`、`yaml檔`、`sql檔`、`cs檔`。
10. Excel 請寫明 `Excel`、`xlsx`、`試算表` 或目標副檔名，例如：「把測試清單做成 Excel 試算表」。
11. 檢查 pending preview 後按「確認寫入」；寫入完成後，對話中會顯示絕對路徑、相對路徑與檔案大小。若檔案沒有實際落檔，後端會回錯，不會顯示成功。

---

## 5. 檔案結構說明

```text
CodeWorker/
├─ config/        # bootstrap、模型 registry 與 aider 設定
├─ data/          # RAG indexes、chat threads、本機 context 選擇與 audit log
├─ docs/          # 截圖、內部文件與測試筆記
├─ downloads/     # bootstrap 下載暫存
├─ logs/          # Web UI、model server 與 context bench log
├─ models/        # GGUF 模型與 mmproj
├─ runtime/       # WinPython、PortableGit、llama.cpp、FFmpeg、whisper.cpp
├─ scripts/       # bootstrap、模型解析、server 啟動與回歸測試
├─ webui/         # Python 後端、RAG/Agent 模組與前端資源
├─ plugins/       # Codex plugin，例如 codeworker-codegraph
├─ THIRD_PARTY_NOTICES.md
├─ VERSION
├─ README.md
├─ README.zh-TW.md
└─ README.en.md
```

重要檔案：

- `config\bootstrap.manifest.json`：runtime、模型來源、`contextWindow`、KV cache type、`mmproj` 與預設設定。
- `scripts\resolve_model_env.py`：依 manifest 解析模型檔、port、context、KV cache type 與 `mmproj`。
- `scripts\launch_llama_server.py`：啟動 bundled `llama.cpp` model server。
- `scripts\run_webui_regression.py`：Web UI、附件、RAG 與 streaming 回歸測試。
- `webui\server.py`：API routes、streaming chat、context assembly、threads、file generation、attachment handling、memory 與 model call。
- `webui\core\hardware.py`：偵測硬體 profile、選擇 backend、推薦模型與產生自動最佳化設定。
- `webui\core\models.py`：模型 registry、狀態與 OpenAI-compatible endpoint 資訊。
- `webui\rag\index.py`：hierarchical project index、SQLite FTS5 fallback、chunk search 與 impact hints。
- `webui\rag\code_graph.py`：CodeGraph-style symbol graph、relationship edges、graph search 與 compact graph context。
- `webui\agent\runtime.py`：ReAct-style Agent、tool calls、pending actions 與 audit log。
- `webui\static\js\app-*.js`：前端 state、API、UI、檔案樹、threads、chat、CodeGraph 與初始化流程。
- `webui\static\styles.css`：450px sidebar、單一 transcript chat、輸入區與 240px thread panel。
- `VERSION`：Web UI 與 `/api/status` 使用的單一版本來源；`scripts\launch-webui.cmd` 也會用它驗證實際啟動版本。
- `plugins\codeworker-codegraph`：repo-local Codex plugin，內含 `codeworker-codegraph` skill 與 `query_codeworker_graph.py` 查詢工具。
- `THIRD_PARTY_NOTICES.md`：第三方出處、作者與授權註記。

---

## 6. 流程架構說明

```mermaid
flowchart LR
    U["使用者"] --> W["Web UI"]
    W --> K["Context selector per model"]
    W --> T["Thread panel"]
    W --> O["Open project / Analyze file structure"]
    O --> I["Local RAG index / CodeGraph"]
    W --> X["CodeGraph query / rescan"]
    W --> P["Pinned files"]
    W --> F["Attachments"]
    W --> G["Model decides file generation"]
    W --> E["Generate edit plan"]
    I --> S["webui/server.py"]
    P --> S
    F --> S
    T --> S
    K --> S
    G --> A["Auto pending preview"]
    E --> V["Validate unique search/replace"]
    V --> B["Pending edit action"]
    O --> H["Transcript tool card"]
    X --> H
    A --> Q["User confirmation"]
    Q --> D["Write generated file"]
    B --> Q2["User confirmation"]
    Q2 --> C1["Git pre-edit checkpoint"]
    C1 --> C2["Apply file operation"]
    C2 --> C3["Git post-edit checkpoint / diff / restore"]
    S --> C["Assemble memory / RAG / pinned context / attachments"]
    C --> M["llama.cpp local model server"]
    M --> R["Streaming reply"]
    R --> H
```

流程重點：

- 沒有開啟專案時，chat payload 只包含使用者問題、附件與對話記憶。
- 開啟專案但沒有 pinned files 時，RAG index 會依問題搜尋相關檔案、symbols、summary 與 chunks。
- `分析專案檔案結構` 與 CodeGraph 查詢只寫入 `transcript`，不會被送進模型 history。
- 有 pinned files 時，會優先使用 pinned context。
- 長回答續寫使用上一段回答 tail，不再重送大型 `PROJECT RAG CONTEXT`。
- 檔案生成由一般聊天觸發；模型先產生內容與標題，CodeWorker 再建立 pending preview。同一句多格式需求會建立多個 preview，文件輸出會清理 Markdown 標記並使用可顯示中文的 PDF 字型。
- 直接修改由 `產生修改計畫` 觸發；模型或本地 deterministic rule 產生 `search/replace`，後端驗證唯一命中後才建立 pending action。
- `確認套用` 前建立 Git pre-edit checkpoint；套用後如果 working tree 變 dirty，建立 post-edit checkpoint，並回傳 diff、changed files、diff stat 與建議驗證指令。
- `VERSION`、`/api/status.appVersion`、`logs\webui-*.log` 開頭的 `RootDir` / `ServerPath` 是更新與部署問題的主要排查來源。

CodeGraph 出處：

- 原始專案：[`colbymchenry/codegraph`](https://github.com/colbymchenry/codegraph)
- 作者 / copyright holder：Colby Mchenry
- 授權：MIT License
- CodeWorker 實作：參考其「本機 symbol graph + relationships + SQLite」工作流，改寫為 Python-native lightweight implementation，詳見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

---

## 7. 版本歷程

### V1.01.002

- 將 Web UI 版本更新為 `CodeWorker V1.01.002`。
- 新增根目錄 `VERSION` 作為單一版本來源；`webui/server.py` 啟動時讀取此檔，`/api/status` 回傳 `appVersion`、`appName`、`rootDir` 與 `serverPath`。
- `scripts\launch-webui.cmd` 會讀取 `VERSION`、等待 `/api/status` 回傳相同版本，並用 `?v=版本-時間戳` 開啟頁面，避免瀏覽器或舊 process 造成更新後仍看到舊版。
- `scripts\bootstrap.ps1` 啟動時會停止同一個 CodeWorker root/runtime 下的舊 process，降低更新 runtime 或 source 後舊 WebUI 仍佔用 port 的機率。
- WebUI log 開頭會印出實際 `RootDir` 與 `ServerPath`；這可用來判斷另一台電腦是否啟動到舊資料夾或舊捷徑。
- `json_response()` 與 `text_response()` 會忽略瀏覽器中途斷線造成的 `BrokenPipeError`、`ConnectionAbortedError`、`ConnectionResetError`，避免 `WinError 10053` 混淆版本問題判讀。
- 新增本地檔案修改工作流：`產生修改計畫`、pending action card、`確認套用`、`查看 Git diff`、`建立 checkpoint` 與 `復原這次修改`。
- 新增 Git safety layer，檔案修改套用前建立 pre-edit checkpoint，套用後若有檔案變更建立 post-edit checkpoint，並限制 restore 只能回到 CodeWorker 建立的 pre-edit checkpoint。
- 新增 `/api/edit/apply`、`/api/edit/status`、`/api/git/diff`、`/api/git/checkpoint`、`/api/git/restore`，支援 `create_file`、`patch_file`、`replace_file`、`delete_file`、`rename_file`、`run_command` pending actions。
- `patch_file` 通用化：本地模型輸出合法 JSON patch 時，CodeWorker 會驗證 `search` 是否唯一命中本機檔案，通過後才建立可套用 action。
- 新增模型 patch salvage：若模型 JSON 不完整，但仍可抽出 `path/search/replace`，且本機驗證安全，仍會建立真正 `patch_file`；無法安全定位時才降級為 advisory。
- 修正安全檢查：程式碼字串 literal 內的新文字不會被誤判為未知 identifier，但真正引入未宣告 identifier 仍會被攔截。
- 套用修改後新增 validation command suggestions，例如 `.sln/.csproj` 建議 `dotnet build`，`package.json` 建議 `npm test` / `npm run build`，但不自動執行任意 build/test script。
- 新增 Tetris 鍵盤行為 deterministic patch 範例：`Down/S` 軟降一格，`Ctrl/ControlKey/LControlKey/RControlKey` 執行 `HardDrop()`；已符合需求時會回覆無需修改，避免重複 patch 或模型逾時。
- 將對話、AI streaming、專案結構分析、CodeGraph 查詢 / 重建、context coverage 與檔案生成確認整合到單一 transcript scroll container。
- 新增 persisted `transcriptVersion: 1` 與 `transcript` thread data；舊 thread 會從既有 `history` fallback 顯示。
- 保留 `history` 作為模型上下文來源，工具卡與狀態卡只進 `transcript`，避免 CodeGraph / 分析結果被誤送進 LLM。
- `分析專案` 重新定位為 `分析專案檔案結構`，用於釘選前分類入口、核心程式、project configs、UI/form、assets、tests、generated files 與 build outputs。
- 擴充多語言分類，納入 Delphi / Object Pascal、C、C++、VB、.NET、JS/TS、Python、Java/Kotlin、Go、Rust、PHP、Ruby 與常見資源目錄。
- CodeGraph 工具列改為使用對話輸入框查詢，查詢結果、no-match 建議、matched files、重建摘要與釘選回饋都插入 transcript。
- 新增 `/api/project/structure`、`/api/codegraph/status`、`/api/codegraph/query` 與 `POST /api/threads/cleanup-empty` 相關 regression coverage。
- 正式加入 `scripts\run_webui_e2e.mjs` 與 `scripts\run_webui_e2e.cmd`，覆蓋 3 輪 browser E2E、thread cleanup、CodeGraph、file tree virtualization、busy indicator 與 responsive layout。
- 新增 `THIRD_PARTY_NOTICES.md`，註明 `colbymchenry/codegraph` 的出處、作者 Colby Mchenry 與 MIT License。
- 新增 V1.01.002 中英文 Web UI 截圖，README 使用最新工作內容畫面。

### V1.01.001

- 新增高階模型選項 `Qwen3-Coder 30B A3B` 與 `GLM-4.6`，以及低階 / 標準備援 `Qwen2.5-Coder 14B Instruct` 與 `DeepSeek-Coder V2 Lite`。
- 新增硬體偵測與自動最佳化設定，會依 RAM、CPU threads、GPU vendor、VRAM、`nvidia-smi` 與 Vulkan 可用性推薦模型、backend、context、threads 與 `--n-gpu-layers`。
- `/api/models` 會回傳 `hardwareProfile`、`recommendedModelKey`、各模型 tier、估計模型大小、runtime backend、GPU layers 與 threads。
- Web UI 模型下拉選單會顯示 tier、模型大小、context 與推薦資訊，左側新增硬體偵測狀態區。
- `scripts\launch_llama_server.py` 支援 `--n-gpu-layers`、`--flash-attn` 與 `--jinja`，不再固定 CPU-only。
- 新增 `logs\hardware-optimization.jsonl` 詳細記錄硬體 profile、模型推薦、啟動計畫、實際 backend、context、threads、GPU layers、模型檔路徑與 log path。
- 每次 `llama-server-*.log` 開頭會寫入 `[CODEWORKER_LAUNCH_METADATA]`，方便回查實際 command 與 llama.cpp 啟動參數。
- 新增 CodeGraph-style 本機語意索引，在 RAG index 內建立 `code_nodes` / `code_edges` / `code_unresolved_refs`，讓模型上下文先取得 symbol 與 relationship map。
- 新增 `plugins\codeworker-codegraph` Codex plugin，可安裝後用 `codeworker-codegraph` skill 與 `query_codeworker_graph.py` 查 CodeWorker 本機 graph。
- 高階硬體尚待實機驗證：CUDA / Vulkan runtime 選擇、`Qwen3-Coder 30B A3B`、`GLM-4.6`、大 context 與 GPU offload 穩定性需由高階 PC 測試後回傳 log 確認。

### V1.01.000

- 新增每模型獨立 `Context` 下拉選單，固定支援 `4k / 8k / 16k / 32k / 64k / 128k / 256k`。
- `Gemma 4 26B` 與 `Qwen 3.5 9B Vision` 預設 context 改為 `256k`，啟動時傳入 `llama-server -c 262144`。
- 新增 KV cache type 設定，預設 `cacheTypeK=q4_0`、`cacheTypeV=q4_0`。
- 新增右側 `240px` 對話串面板，支援新增、切換、重新命名與刪除 thread。
- 新增 file generation pending workflow，支援 text/code、`.docx`、`.pdf`、`.pptx`、`.xlsx`。
- 移除前端 `生成檔案` 按鈕，檔案生成改由模型在一般聊天中判斷並發起。
- 檔名改由模型回覆的第一個 Markdown H1 標題自動命名，寫入完成後顯示實際檔案路徑。
- 修正「請把剛剛的回答生成word檔」被誤判為續寫的問題，Word 生成會正確建立 `.docx` pending preview。
- 補齊純文字與程式碼格式別名，支援 `txt檔`、`md檔`、`py檔`、`js檔`、`ts檔`、`json檔`、`html檔`、`css檔`、`yaml檔`、`sql檔`、`cs檔` 等自然語言寫法。
- 新增同則訊息內嵌內容生成流程；使用者貼上完整 Markdown 並要求 `.docx` 等格式時，CodeWorker 直接建立 preview，不再消耗模型推理。
- 新增上一則回答直接生成流程；使用者要求「上面的內容 / 剛剛的回答」輸出成文件時，CodeWorker 直接取 history 建立 preview，不再消耗模型推理。
- 檔案確認寫入後會驗證實體檔案存在並回傳絕對路徑與大小；前端成功訊息改顯示絕對路徑，避免相對路徑造成誤判。
- 檔案生成可解析「PPTX 跟 PDF」等多格式需求，並在提到「剛剛 / 上一則」時使用上一則 assistant 可見回答當內容來源。
- 修正 PDF 中文亂碼、PPTX / DOCX 暴露 Markdown 標記，以及「把說明生成 Word 檔」未使用上一則回答的問題。
- `scripts\bootstrap.ps1` 新增 `pdfplumber`、`reportlab`、`python-pptx` 與 `openpyxl`。
- README、流程圖、檔案結構與使用教學更新到 V1.01.000。

### V1.00.000

- 預設模型改為 `Gemma 4 26B`，`Qwen 3.5 9B Vision` 保留為可選備用模型。
- Gemma4 改用 Unsloth GGUF 與 bundled `llama.cpp`，並檢查實際 `model_path` 與 vision `mmproj` 狀態。
- 新增全專案 RAG 搜尋，未釘選檔案也能找相關檔案、片段與行號。
- 新增通用附件流程：文件抽文字、圖片 native vision、影片 keyframes、音訊 / 影片音軌 speech-to-text，失敗時提供 metadata fallback。
- 新增壓縮式對話記憶與最近多輪原文，改善追問連貫並降低 token 使用量。
- 修正長回答截斷與「請繼續」問題。
- 思考過程改為預設摺疊，展開時自動捲到最新輸出。
- 移除右側檔案預覽面板，改為 450px sidebar 與單欄寬版 chat。

### V0.98b

- `Gemma 4` 從 E4B 更新為 26B GGUF，改由 CodeWorker 內建 `llama.cpp` service 服務，不依賴 Ollama。
- 一般聊天解除「必須開啟專案 / 必須釘選檔案」限制。
- 新增 `/api/chat/stream`，顯示 streaming content 與 reasoning/thinking 輸出。
- 新增本機 RAG index、Agent v1 API、pending action 確認與 audit log。

### V0.97b

- 主對話框與 `分析專案` 收斂為較接近模型原始輸出的 `raw-first` 路線。
- 修正大型 pinned file 僅剩檔名、內容不足的問題。

### V0.96b

- README landing page、中英文文件與 UI 對齊。

### V0.95b

- 建立 README landing page 與雙語文件分流。
- Web UI 新增 `繁中 / EN` 語言切換。

### V0.94b

- 移除舊的修改建議 modal。
- 所有分析與修正迭代回到主對話框。

---

## 8. 版權宣告

本專案採用 [MIT](LICENSE) 授權。

CodeGraph 相關註記：

- CodeWorker 的 CodeGraph-style 功能參考 [`colbymchenry/codegraph`](https://github.com/colbymchenry/codegraph) 的本機語意索引與 graph-first exploration 工作流。
- `colbymchenry/codegraph` 作者 / copyright holder 為 Colby Mchenry，採 MIT License。
- CodeWorker 目前未 vendoring 上游 TypeScript package；本專案以 `webui\rag\code_graph.py` 提供 Python-native lightweight implementation。
- 詳細第三方出處與授權請見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

在客戶端、內網或 air-gapped environment 使用本工具時，仍需自行確認：

- 本地模型與第三方 runtime 的授權條件。
- 客戶環境對 USB、可攜式工具與 offline AI 的使用規範。
- 目標專案與資料是否允許被本機模型讀取。
