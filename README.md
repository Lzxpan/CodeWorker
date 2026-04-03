# CodeWorker V0.92b

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
- 完成下載後可離線使用

---

## 2. 目錄結構

```text
CodeWorker/
  config/
  logs/
  models/
    codellama-7b-instruct-q4/
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

### 基本操作流程

1. 按 `選擇資料夾`
2. 選擇你的專案根目錄
3. 確認模型是 `Qwen 2.5 Coder 7B`
4. 按 `開啟專案`
5. 等進度條完成
6. 先按 `分析專案` 看整體架構
7. 若要讓模型直接改檔，先在 `檔案樹` 勾選相關檔案並按 `套用釘選`
8. 在 `對話` 輸入修改需求，按 `產生修改草案`
9. 先檢查 `修改草案` 區的摘要與 diff，確認後按 `套用修改`
10. 若只想討論或分析，再到 `對話` 區提問即可

---

## 5. Web UI 各功能說明

### 專案路徑

這是目前要分析的專案資料夾。

- 建議選專案根目錄
- 不要選整個下載資料夾或大量影音資源資料夾
- 路徑可手動輸入，也可用 `選擇資料夾`

### 選擇資料夾

開啟 Windows 原生資料夾選取視窗。

- 用滑鼠選目錄比較不容易打錯
- 選完後路徑會自動填入

### 模型

目前支援兩個模型：

- `Qwen 2.5 Coder 7B`
  - 預設模型
  - 中文表現較好
  - 建議一般使用都選它
- `Code Llama 7B`
  - 備援模型
  - 中文互動通常較弱

### 開啟專案

這是正式載入專案的按鈕。它會：

- 檢查專案路徑
- 確認 git 狀態
- 必要時建立 `.git`
- 啟動本地模型 server
- 掃描專案檔案
- 建立專案摘要與檔案樹

### 分析專案

要求模型先對專案做整體分析。

常見用途：

- 找入口檔案
- 找核心模組
- 找設定檔
- 找測試位置
- 快速理解專案結構

### 專案摘要

這是系統對目前專案整理出的總覽，不是原始碼。

通常會看到：

- 專案路徑
- 已掃描檔案數量
- 估計文字檔總大小
- 主要語言分布
- 可能入口檔案
- 測試相關檔案

適合用來快速確認：

- 你有沒有選對資料夾
- 這個專案大概是什麼技術棧

### 檔案樹

這是目前載入的檔案清單。

可以做兩件事：

- 點檔名：在 `檔案預覽` 看內容
- 勾選檔案：把它加入釘選上下文

### 套用釘選

把你在檔案樹勾選的檔案設成優先上下文。

作用是讓模型之後分析或對話時，優先參考這些檔案。

適合情境：

- 你只想聚焦某幾個模組
- 你知道 bug 大概在哪幾個檔案
- 你不想讓模型讀太多不相干內容

### 檔案預覽

這是檔案內容閱讀區，不是編輯器。

- 點檔案樹中的檔案後，內容會顯示在這裡
- 用來快速確認這個檔案是不是你要的
- 內容過長時會在區塊內捲動，不會把整頁拉長

### 對話

這是你和模型互動的主要區域。

可以問：

- `請分析登入流程涉及哪些檔案？`
- `這個專案的入口在哪裡？`
- `先不要改檔，先分析這個 bug 可能在哪幾個模組`
- `請根據目前釘選檔案說明 API flow`

### 產生修改草案

這個按鈕會根據目前輸入框的內容，請模型先產生一份「尚未寫入」的修改提案。

建議流程：

- 先在 `檔案樹` 勾選你想改的檔案
- 按 `套用釘選`
- 在 `對話輸入` 寫清楚修改需求
- 按 `產生修改草案`

系統會顯示：

- 修改摘要
- 需要修改的檔案
- unified diff 預覽

### 修改草案

這是 `Web UI` 目前真正的改檔入口。

它的用途是：

- 先讓你看模型準備怎麼改
- 不直接裸寫檔案
- 讓你確認內容後再套用

目前版本限制：

- 只支援修改既有的文字檔
- 不支援新增檔案
- 不支援刪除檔案
- 最穩定的作法仍是先釘選目標檔案，再產生草案

### 套用修改

這個按鈕會把目前的 `修改草案` 正式寫回專案檔案。

套用後系統會：

- 寫入修改後的檔案內容
- 執行 `git add`
- 嘗試自動建立一次 commit

### 丟棄草案

如果草案不滿意，可以直接丟棄。

- 不會改動任何檔案
- 只會清掉目前待套用的草案
- 之後可以重新生成新的草案

### 送出

把目前輸入框的內容送給模型。

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

## 7. 頁面捲動方式

目前 UI 已調整成盡量維持在單一畫面內：

- `專案摘要` 可在自己的區塊內捲動
- `檔案樹` 可在自己的區塊內捲動
- `檔案預覽` 可在自己的區塊內捲動
- `對話` 可在自己的區塊內捲動
- `修改草案` 的 diff 預覽可在自己的區塊內捲動

這樣長內容不會一直把整頁越拉越長。

---

## 8. CLI 使用方式

如果你不想用 web UI，也可以直接用命令列。

### 啟動本地模型 server

```cmd
scripts\start-server.cmd
```

改用 Code Llama：

```cmd
scripts\start-server.cmd codellama
```

### 開啟專案級 code chat

```cmd
scripts\code-chat.cmd C:\path\to\project
```

改用 Code Llama：

```cmd
scripts\code-chat.cmd C:\path\to\project codellama
```

用 browser 模式：

```cmd
scripts\code-chat.cmd C:\path\to\project qwen --browser
```

---

## 9. 腳本用途

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
- 修改草案產生
- 修改草案套用

---

## 10. 常見使用流程

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

### 情境 C：直接修改專案檔案

1. 開啟專案
2. 在 `檔案樹` 勾選要修改的檔案
3. 按 `套用釘選`
4. 在 `對話輸入` 寫明確修改需求
5. 按 `產生修改草案`
6. 先檢查 `修改草案` 區的 diff
7. 確認後按 `套用修改`

### 情境 D：模型有問題

1. 看 `錯誤訊息`
2. 若顯示模型檔問題，按 `重新下載模型`
3. 下載完成後再按 `開啟專案`

---

## 11. 已知限制

- 目前只支援 Windows x64
- 建議至少 16GB RAM
- 第一次準備環境需要網路
- `Web UI` 目前可直接修改既有文字檔，但不支援新增檔案或刪除檔案
- 若修改需求跨很多檔案或需要大型 refactor，仍建議使用 `scripts\code-chat.cmd`

---

## 12. 建議驗收

```cmd
scripts\bootstrap.cmd
scripts\install-aider.cmd
scripts\launch-webui.cmd
scripts\start-server.cmd
scripts\code-chat.cmd C:\some\repo
```

確認：

- 模型可成功啟動
- 可開啟含繁體中文路徑的專案
- `專案摘要`、`檔案樹`、`檔案預覽`、`對話`、`修改草案` 都能正常使用
- 長內容時會在區塊內捲動，不會讓整頁無限拉長
- 可產生修改草案並成功套用到既有專案檔案

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
