# CodeWorker V0.95b

> GitHub Repository: [Lzxpan/CodeWorker](https://github.com/Lzxpan/CodeWorker)

`CodeWorker` 是一套可放在 USB 隨身碟上的 Windows 離線 code assistant。  
它把 `llama.cpp`、`WinPython`、`PortableGit`、GGUF 模型與本地 web UI 包成一個可攜式工作目錄，目標是：

- 在不同 Windows 電腦上直接執行
- 可離線分析整個專案資料夾，而不是只看單檔
- 能用繁體中文對話、分析、解釋與協助修改程式碼

---

## 1. 系統需求

- Windows 10 / 11 x64
- 建議至少 16GB RAM
- 建議 CPU 支援 AVX2
- 第一次下載 runtime / 模型時需要網路
- 第一次下載的總檔案大小會超過 5GB，依網路速度與 USB / 硬碟寫入速度不同，可能需要一段時間，請耐心等待
- 若啟用第三模型 `Gemma 4 E4B`，首次下載量與磁碟占用會再增加
- 完成下載後可離線使用

---

## 2. 目錄結構

```text
CodeWorker/
  config/
  logs/
  models/
    codellama-7b-instruct-q4/
    gemma4-e4b-it-q4/
    qwen2.5-coder-7b-instruct-q4/
  runtime/
    PortableGit/
    WinPython/
    llama.cpp/
  scripts/
  webui/
```

---

## 3. 安裝方式

### 作法 0：從 GitHub 取得

如果你要從 GitHub 下載或同步這個專案，可用：

```cmd
git clone https://github.com/Lzxpan/CodeWorker.git
cd CodeWorker
```

如果是已經放進 USB 隨身碟的版本，直接複製整個 `CodeWorker` 資料夾即可，不一定要重新 clone。

### 作法 A：直接自動下載必要元件

在 `CodeWorker` 根目錄執行：

```cmd
scripts\bootstrap.cmd
```

這會自動處理：

- 下載 `llama.cpp`
- 下載 `PortableGit`
- 下載 `WinPython 3.12`
- 下載預設 Qwen GGUF 模型
- 下載 `Gemma 4 E4B` 對應的官方 GGUF 模型

如果你之後想用 CLI agent，再執行：

```cmd
scripts\install-aider.cmd
```

`scripts\install-aider.cmd` 會自動檢查 portable Python 版本；若目前是 `Python 3.13+`，會自動重裝成與 `aider-chat` 相容的 `WinPython 3.12` 後再安裝。

### 作法 B：第一次直接開 Web UI，缺什麼就補什麼

```cmd
scripts\launch-webui.cmd
```

若本機還沒有 runtime 或模型，系統會在第一次開專案時自動補齊。

### 作法 C：手動放入 runtime 與模型

如果你已經有現成檔案，可以手動放到以下目錄：

- `runtime\llama.cpp\`
  - 放 `llama-server.exe` 與相關 DLL
- `runtime\WinPython\`
  - 放 portable Python
  - 需可執行 `python.exe`
- `runtime\PortableGit\`
  - 放 PortableGit
  - 需包含 `cmd\git.exe` 或 `bin\git.exe`
- `models\qwen2.5-coder-7b-instruct-q4\`
  - 放 Qwen GGUF
- `models\gemma4-e4b-it-q4\`
  - 放 `ggml-org/gemma-4-E4B-it-GGUF` 的 GGUF
- `models\codellama-7b-instruct-q4\`
  - 放 Code Llama GGUF

---

## 4. 最快開始方式

### 啟動本地網頁介面

```cmd
cd /d C:\Users\Admin\Desktop\CodeWorker
scripts\launch-webui.cmd
```

瀏覽器會開啟：

```text
http://127.0.0.1:8764
```

### Web UI 畫面範例

以下畫面是已開啟專案後的 `Web UI` 主要介面，實際顯示內容會依目前專案、釘選檔案與對話狀態不同而略有差異。

![CodeWorker Web UI 畫面總覽](docs/screenshots/webui-overview.png)

下面這張畫面則是「專案已開啟、摘要與檔案樹已載入、可以開始勾選與套用釘選」的狀態。

![CodeWorker Web UI 已開啟專案與檔案樹](docs/screenshots/webui-pinned-workspace.png)

### 畫面導覽

上圖可以先用這個方式理解：

- 左側欄：
  - `專案路徑`、`模型`、`開啟專案`、`分析專案`
  - `專案摘要`
  - `檔案樹`
- 中間主區：
  - `對話` 歷史
  - `對話輸入`
  - `送出`、`清空對話`
  - 之後所有修改建議、修正回合、分析結果，都會直接顯示在這裡
- 右側欄：
  - `檔案預覽`
  - 只負責閱讀檔案內容，不會自動成為模型上下文

### 基本操作流程

1. 點一下 `專案路徑` 欄位
2. 選擇你的專案根目錄
3. 確認模型是你要使用的模型，預設建議先用 `Qwen 2.5 Coder 7B`
4. 按 `開啟專案`
5. 等進度條完成
6. 在 `檔案樹` 勾選要給模型看的檔案
7. 按 `套用釘選`
8. 先按 `分析專案`，或直接在 `對話` 區提問
9. 若要模型提供修改建議，直接在 `對話輸入` 寫修改需求後按 `送出`
10. 修改建議、局部 diff、修正說明都會直接顯示在主對話框
11. 若建議有錯，直接在同一個主對話框接著描述問題，例如 `piece 不存在，請改用現有變數`
12. 若你想整個重來，再按 `清空對話`

### 用畫面對照操作順序

如果你是第一次使用，建議直接照這個順序對照畫面：

1. 左上 `專案路徑`：點一下欄位，選專案資料夾
2. 左上 `模型`：預設先維持 `Qwen 2.5 Coder 7B`，若要對照評估再切換到 `Gemma 4 E4B`
3. 左上按 `開啟專案`
4. 左下 `檔案樹`：勾選你要讓模型讀取的檔案
5. 左下按 `套用釘選`
6. 中間 `對話輸入`：直接輸入分析需求或修改需求
7. 中間按 `送出`
8. 查看中間 `對話` 區的分析結果、修改建議與 diff

重點是：

- 現在沒有獨立的 `產生修改建議` 按鈕
- 也沒有獨立的修改建議視窗
- 只要在主對話框輸入明確修改需求後按 `送出`，系統就會直接回修改建議

---

## 5. Web UI 各功能說明

你可以先對照上面的畫面截圖，再閱讀下面各區塊的用途。

### 專案路徑

這是目前要分析的專案資料夾。

- 建議選專案根目錄
- 不要選整個下載資料夾或大量影音資源資料夾
- 直接點一下欄位，就會開啟 Windows 原生資料夾選取視窗
- 選完後路徑會自動填入

### 模型

目前支援三個模型：

- `Qwen 2.5 Coder 7B`
  - 預設模型
  - 中文表現較好
  - 建議一般使用都選它
- `Gemma 4 E4B`
  - 新增可選模型
  - 採用官方 `ggml-org/gemma-4-E4B-it-GGUF` 路線
  - 適合做對照評估，不建議直接取代 Qwen
  - 目前 `edit plan` 已改成較保守的 `locator -> patch -> advisory fallback` 路線
  - 目前定位是現有 CPU / USB 架構下的輕量評估模型，不是主要修改建議模型
- `Code Llama 7B`
  - 備援模型
  - 中文互動通常較弱

### `Gemma 4` 與硬體的關係

`Gemma 4 E4B` 不如預期，不應只歸因於硬體不足。

- 目前影響最大的，是模型尺寸、chat template / prompt 對齊程度，以及結構化 `edit plan` 任務本身的難度
- 硬體主要影響的是：
  - 啟動速度
  - 推理速度
  - 可承受的 context
  - 能不能改用更大的 `Gemma 4` 型號
- 換句話說：
  - 更高階硬體不太會把 `Gemma 4 E4B` 直接變成強結構化 code-edit 模型
  - 但更高階硬體有機會讓你評估 `Gemma 4 31B` 或 `Gemma 4 26B A4B`

### 高階硬體建議

如果你未來有更高階的 GPU 或更大的記憶體，建議優先評估：

- `Gemma 4 31B`
- `Gemma 4 26B A4B`

這兩個型號在官方 benchmark 與社群 local coding 測試中，都比 `Gemma 4 E4B` 更有機會成為可用的 coding / edit 模型。  
目前 `CodeWorker` repo 尚未把它們接進預設下載流程，這一版只先保留為後續高階硬體候選路線。

### 開啟專案

這是正式載入專案的按鈕。它會：

- 檢查專案路徑
- 確認 git 狀態
- 必要時建立 `.git`
- 啟動本地模型 server
- 掃描專案檔案
- 建立專案摘要與檔案樹

### 分析專案

要求模型先對「目前已套用的釘選檔案」做整體分析。

常見用途：

- 找入口檔案
- 找核心模組
- 找設定檔
- 找測試位置
- 快速理解專案結構

注意：

- 若尚未套用任何釘選檔案，系統會先要求你去 `檔案樹` 勾選並按 `套用釘選`

### 專案摘要

這是系統對目前專案整理出的總覽，不是原始碼。

通常會看到：

- 專案路徑
- 已掃描檔案數量
- 估計文字檔總大小
- 主要語言分布
- 可能入口檔案
- 測試相關檔案
- 已套用釘選檔案清單

適合用來快速確認：

- 你有沒有選對資料夾
- 這個專案大概是什麼技術棧

### 檔案樹

這是目前載入的檔案清單。

可以做兩件事：

- 點檔名：在 `檔案預覽` 看內容
- 勾選檔案：把它加入釘選清單

### 套用釘選

把你在檔案樹勾選的檔案設成模型目前唯一的上下文來源。

作用是讓模型之後分析、對話與修改建議都只根據這些檔案回答。

適合情境：

- 你只想聚焦某幾個模組
- 你知道 bug 大概在哪幾個檔案
- 你不想讓模型讀太多不相干內容

### 檔案預覽

這是檔案內容閱讀區，不是編輯器，也不是模型上下文來源。

- 點檔案樹中的檔案後，內容會顯示在這裡
- 用來快速確認這個檔案是不是你要的
- 這裡的內容不會自動送給模型
- 若要讓模型真的讀取該檔案，仍需在 `檔案樹` 勾選後按 `套用釘選`
- 內容過長時會在區塊內捲動，不會把整頁拉長

### 對話

這是你和模型互動的主要區域。

可以問：

- `請分析登入流程涉及哪些檔案？`
- `這個專案的入口在哪裡？`
- `先不要改檔，先分析這個 bug 可能在哪幾個模組`
- `請根據目前釘選檔案說明 API flow`

注意：

- `對話` 只會根據目前已套用的釘選檔案回答
- `檔案預覽` 只是閱讀，不會自動加入上下文
- 若尚未套用任何釘選檔案，系統會先要求你去 `檔案樹` 勾選並按 `套用釘選`
- 若你輸入的是明確修改需求，這裡也會直接顯示修改建議、局部 diff 與修正回合

### 送出

把目前輸入框的內容送給模型。

- 一般分析需求會回一般分析結果
- 修改需求會直接在主對話框回覆修改建議與 diff
- 若上一版建議有錯，直接在同一個主對話框說明，系統會把它當成修正上一版建議
- 目前所有「分析 / 建議 / 修正」都統一走這個按鈕

### 清空對話

清掉目前頁面上的對話紀錄。

- 不會刪除專案
- 不會刪除模型
- 不會刪除摘要或檔案樹

### 錯誤訊息

如果模型啟動失敗、下載失敗、路徑錯誤或對話出錯，這裡會顯示：

- 錯誤碼
- 錯誤摘要
- 詳細內容
- log 路徑

### 重新下載模型

當模型檔損壞、下載不完整、或讀取失敗時，用這個按鈕重新下載模型。

---

## 6. 介面上的 `?` 說明按鈕

現在每個主要功能旁都會有 `?`。

點下去會顯示：

- 這個功能是做什麼的
- 何時該用
- 一般使用步驟

如果你不確定某個欄位或按鈕用途，先點 `?` 看說明即可。

--- 

## 7. 上下文規則

目前版本的 `Web UI` 採用固定規則：

- `檔案釘選` 是唯一的模型上下文來源
- `檔案預覽` 只負責顯示內容，不會自動加入模型上下文
- `對話 / 分析專案` 都只看目前已套用的釘選檔案
- 修改建議不再有獨立按鈕，而是直接透過主對話框的修改需求產生

建議操作順序：

1. 開啟專案
2. 在 `檔案樹` 勾選要給模型看的檔案
3. 按 `套用釘選`
4. 再進行 `分析專案` 或在 `對話` 區輸入需求

如果你沒有先套用釘選檔案，系統會直接提示你先完成這一步。

---
## 8. 頁面捲動方式

目前 UI 已調整成盡量維持在單一畫面內：

- `專案摘要` 可在自己的區塊內捲動
- `檔案樹` 可在自己的區塊內捲動
- `檔案預覽` 可在自己的區塊內捲動
- `對話` 可在自己的區塊內捲動
- 修改建議與修正回合也都直接顯示在 `對話` 區內

這樣長內容不會一直把整頁越拉越長。

---

## 9. CLI 使用方式

如果你不想用 web UI，也可以直接用命令列。

### 啟動本地模型 server

```cmd
scripts\start-server.cmd
```

改用 Code Llama：

```cmd
scripts\start-server.cmd codellama
```

改用 Gemma 4：

```cmd
scripts\start-server.cmd gemma4
```

### 開啟專案級 code chat

```cmd
scripts\code-chat.cmd C:\path\to\project
```

改用 Code Llama：

```cmd
scripts\code-chat.cmd C:\path\to\project codellama
```

改用 Gemma 4：

```cmd
scripts\code-chat.cmd C:\path\to\project gemma4
```

用 browser 模式：

```cmd
scripts\code-chat.cmd C:\path\to\project qwen --browser
```

---

## 10. 腳本用途

### `scripts\bootstrap.cmd`

負責第一次下載與準備 runtime / 模型。

### `scripts\install-aider.cmd`

把 `aider-chat` 安裝到 portable Python。

- 若現有 portable Python 不相容，會自動換成 `WinPython 3.12`
- 安裝完成後可用於 `scripts\code-chat.cmd`

### `scripts\attach-project.cmd`

處理專案的 git 準備：

- 檢查是否已有 `.git`
- 沒有就 `git init`
- 建立初始 snapshot
- 自動加上排除規則，避免大型 binary 拖慢流程

### `scripts\start-server.cmd`

用 CLI 方式啟動 `llama-server.exe`。

### `scripts\code-chat.cmd`

用 `aider` 對整個 repo 做分析與互動。

### `scripts\launch-webui.cmd`

啟動本地 web UI。

### `webui\server.py`

負責：

- web UI API
- 原生資料夾選取
- 開專案背景任務
- 模型啟動
- 專案掃描
- 檔案預覽
- 專案分析
- 對話
- 修改建議產生
- 修改建議修正上下文

---

## 11. 常見使用流程

### 情境 A：第一次拿到新專案

1. 啟動 web UI
2. 選專案資料夾
3. 按 `開啟專案`
4. 按 `分析專案`
5. 看 `專案摘要`
6. 看 `檔案樹`
7. 點幾個入口檔案到 `檔案預覽`
8. 再開始提問

### 情境 B：只想看某幾個檔案

1. 開啟專案
2. 在 `檔案樹` 勾選幾個檔案
3. 按 `套用釘選`
4. 到 `對話` 問問題

### 情境 C：請模型提供修改建議

1. 開啟專案
2. 在 `檔案樹` 勾選要修改的檔案
3. 按 `套用釘選`
4. 在 `對話輸入` 寫明確修改需求
5. 按 `送出`
6. 直接在主對話框查看摘要、修改位置與 diff
7. 若建議有錯，在同一個主對話框接著描述錯誤點
8. 若你想完全換一輪思考，再按 `清空對話`

你可以對照第一張截圖理解這個流程：

- 中間 `對話` 區會直接顯示模型建議
- 若模型已定位到方法或區塊，通常會附上檔案、行數範圍與局部 diff
- 你不需要另外打開視窗或切換模式

### 情境 E：如何修正上一版錯誤建議

1. 不要切換頁面，也不需要另外開視窗
2. 直接在主對話框往下輸入你發現的問題
3. 建議描述方式要具體，例如：
   - `piece 不存在，請改用目前 Form1.cs 裡真的有的變數`
   - `不要插在 case Keys.Down 下面，應該改用 HardDrop()`
   - `請只修改 Form1_KeyDown，不要動其他函式`
4. 按 `送出`
5. 系統會把上一版建議當成修正對象，再產生下一輪結果

### 情境 D：模型有問題

1. 看 `錯誤訊息`
2. 若顯示模型檔問題，按 `重新下載模型`
3. 下載完成後再按 `開啟專案`

---

## 12. 版本歷程

### V0.95b

- 將目前 repo 內已完成但尚未發布的 `Gemma 4 E4B` 支援與穩定化調整收斂成正式版本
- 同步更新專案版號，作為後續雙語 README 與 UI 語言切換的基線版本

### V0.94b

- 移除 `修改建議` 的 modal / 獨立視窗
- 改成所有分析、建議、修正回合都回到主對話框
- `送出` 現在同時承擔一般分析與修改建議請求
- `清空對話` 會同步清掉目前的 `pendingEdit`
- 修正 live `H:\CodeWorker` 與工作目錄版本容易不同步的使用流程
- README 新增 Web UI 截圖與畫面導覽說明
- 新增真正的 `Gemma 4 E4B` 作為第三個可選模型，保留 `Qwen` 為預設
- 針對 `Gemma 4 E4B` 的 `create_edit_plan()` 補上較保守的單筆扁平 schema 與 JSON 容錯，降低結構化建議失敗率
- `Gemma 4` 改為較接近官方格式的訊息組裝方式，並加入 `precise -> advisory -> text fallback` 降級流程
- 當 `Gemma 4` 無法產生合法 JSON 時，改由本地區段定位補出 `path / target / location / 區段原文`，避免只剩空白錯誤
- `Gemma 4 E4B` 的 `edit plan` 進一步改成 `locator -> patch -> advisory fallback` 兩段式流程，降低單次結構化輸出失敗率
- `README` 新增 `Gemma 4 E4B` 與硬體的關係說明，明確區分 `E4B` 與高階硬體下可評估的 `Gemma 4 31B / 26B A4B`

### V0.93b

- 改善單檔釘選時的區段命中，避免模型一直只看到檔案開頭
- 修改建議輸出改成更偏向局部 hunk 與命中函式/區塊
- 強化 `chat` 與 `edit plan` 的 C# 區段定位

### V0.92b

- 調整 `Web UI` 直接改檔策略，改為較安全的建議 / 預覽導向
- 修正 `bootstrap` / `install-aider` 的 `WinPython 3.12` 相容路徑

### V0.91b

- 建立早期 `Web UI` 版面與專案開啟流程
- 新增 `專案摘要`、`檔案樹`、`檔案預覽`、`對話` 等主要介面區塊

---

## 13. 重點提醒

- `檔案預覽` 只是閱讀區，不是模型上下文來源。
- 一切分析與修改建議都只根據 `已套用釘選檔案`。
- 目前 `Web UI` 不會直接寫回專案檔案，仍以建議與 diff 預覽為主。
- 如果模型給的修改建議有錯，直接在同一個主對話框接著描述問題，不需要切換視窗。
- 目前畫面上只保留 `送出` 與 `清空對話` 兩個主要互動按鈕；修改建議已整合進主對話流程。
- 目前不支援截圖貼上、OCR 或 Vision 模型整合；錯誤回報請先用文字描述。
- 若需求跨很多檔案、需要大型 refactor，優先考慮 `scripts\code-chat.cmd`。
- `Gemma 4 E4B` 目前是新增可選模型，不建議在未完成品質對照前取代 `Qwen 2.5 Coder 7B`。
- `Gemma 4 E4B` 已完成官方 GGUF / `llama.cpp` 啟動驗證，但目前在結構化 `修改建議` 與 refine 穩定性上仍弱於 `Qwen 2.5 Coder 7B`，因此仍建議把 `Qwen` 保留為預設模型。
- `Gemma 4 E4B` 的 `edit plan` 目前採較保守的 `locator -> patch -> advisory fallback` 路線；若需要高穩定度的修改建議，仍優先建議使用 `Qwen 2.5 Coder 7B`。
- `Gemma 4 E4B` 的問題不應只歸因於硬體不足；硬體主要影響速度、可承受 context、以及是否能評估更大的 `Gemma 4` 型號。
- 若有更高階 GPU 或更大記憶體，後續較值得評估的是 `Gemma 4 31B` 或 `Gemma 4 26B A4B`，而不是期待 `Gemma 4 E4B` 在同樣任務上直接超越 `Qwen 2.5 Coder 7B`。

---

## 14. 已知限制

- 目前只支援 Windows x64
- 建議至少 16GB RAM
- 第一次準備環境需要網路
- `Web UI` 目前以「修改建議 / diff 預覽」為主，不直接寫回專案檔案
- 若修改需求跨很多檔案或需要大型 refactor，仍建議使用 `scripts\code-chat.cmd`

---

## 15. 建議驗收

```cmd
scripts\bootstrap.cmd
scripts\install-aider.cmd
scripts\launch-webui.cmd
scripts\start-server.cmd
scripts\start-server.cmd gemma4
scripts\code-chat.cmd C:\some\repo
scripts\code-chat.cmd C:\some\repo gemma4
```

確認：

- 模型可成功啟動
- 可開啟含繁體中文路徑的專案
- `專案摘要`、`檔案樹`、`檔案預覽`、`對話`、`修改建議` 都能正常使用
- 長內容時會在區塊內捲動，不會讓整頁無限拉長
- 可在主對話框產生修改建議並正常顯示 diff 預覽
- `Gemma 4 E4B` 與 `Qwen` 可在同一組 pinned files 和同一組題目下做對照評估

實際評估重點：

- `Gemma 4 E4B` 已證實可在 `llama.cpp + GGUF + Windows 本機 + USB` 這條架構下啟動
- `Gemma 4 E4B` 的專案入口判讀與單檔函式名稱定位可用
- 但在 `修改建議` 的結構化 JSON 輸出與 refine 回合穩定性，目前仍明顯不如 `Qwen 2.5 Coder 7B`
- 因此現階段建議：
  - 預設仍使用 `Qwen 2.5 Coder 7B`
  - `Gemma 4 E4B` 作為對照評估或特殊需求時的可選模型

---

## 13. License

本專案採用 `MIT License`。

你可以：

- 自由使用
- 修改
- 散布
- 用於商業用途

你需要保留：

- 原始著作權聲明
- `MIT License` 條文

完整授權條文請見：

```text
LICENSE
```
