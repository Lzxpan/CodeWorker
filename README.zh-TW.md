# CodeWorker V0.98b

> 離線、可攜、以隱私與資安為優先的 Windows 本地 AI code assistant。

[English](README.en.md) | [README 首頁](README.md)

`CodeWorker` 是一套可放在 USB 隨身碟上的 **offline AI / local LLM / USB portable** 開發工具。  
它把 `llama.cpp`、`WinPython`、`PortableGit`、GGUF 模型與本地 Web UI 包成一個可攜式工作目錄，適合：

- 客戶端無法上網
- 原始碼不能外流
- 內網或 air-gapped environment
- 需要 on-premise 的 secure code analysis
- 希望在 Windows 本機使用 privacy-first 的 offline coding assistant

---

## 1. 系統需求

- Windows 10 / 11 x64
- `32GB RAM` 是較穩妥的建議目標，特別是較大的本地模型
- 若使用內顯，共用記憶體可能會影響模型實際可用的系統 RAM
- 是否足夠仍需依使用者的實際硬體配置與執行負載自行判斷
- 建議 CPU 支援 AVX2
- 第一次下載 runtime / 模型時需要網路
- 第一次下載的總檔案大小會超過 5GB，依網路速度與 USB / 硬碟寫入速度不同，可能需要一段時間，請耐心等待
- 新版預設下載組合在移除 `Qwen 2.5` 後，整體工作區約為 **11.6 GB**
- 若舊環境仍保留已移除的 `qwen25` 模型檔，整個工作區仍可能接近舊版的 **16.6 GB**
- 要真正釋放這部分空間，仍需實際刪除本機殘留的 `qwen2.5` 模型資料夾
- 完成下載後可離線使用

---

## 2. 模型定位

- `Qwen 3.5 9B Vision`
  - 預設與主力模型
  - 同時支援文字與圖片
  - 目前作為主要的 code 分析與專案聊天模型
- `Gemma 4 E4B`
  - 第二模型，可選使用
  - 已完成 `llama.cpp + GGUF + Windows 本機 + USB` 架構驗證
  - 目前以文字分析為主；本專案現行 `llama.cpp + GGUF` 路線尚未把圖片輸入列為正式支援
  - 目前可啟動、可定位，但修改建議穩定性仍弱於 `Qwen 3.5`

---

## 3. 安裝方式

### 方式 A：第一次完整準備

```cmd
scripts\bootstrap.cmd
```

這會自動處理：

- 下載 `llama.cpp`
- 下載 `PortableGit`
- 下載 `WinPython`
- 下載預設模型

### 方式 B：如果你要用 CLI agent

```cmd
scripts\install-aider.cmd
```

---

## 4. 最快開始方式

### 啟動 Web UI

```cmd
scripts\launch-webui.cmd
```

開啟：

```text
http://127.0.0.1:8764
```

### Web UI 畫面範例

![CodeWorker V0.98b 繁中 Web UI 畫面範例](docs/screenshots/webui-overview-zh-v097b.png)

---

## 5. Web UI 使用流程

1. 點 `專案路徑`
   - 直接選擇你的專案根目錄
2. 確認模型
   - 預設建議直接使用 `Qwen 3.5 9B Vision`
3. 按 `開啟專案`
4. 在 `檔案樹` 勾選你要讓模型讀取的檔案
5. 勾選後會立即同步釘選狀態
6. 在主對話框直接提問或描述修改需求

若要做圖片辨識：

7. 在主對話框下方點 `上傳圖片`，或直接貼上截圖
8. 請確認目前選定模型本身支援圖片；目前正式支援圖片的是 `Qwen 3.5 9B Vision`
9. 可直接詢問圖片內容，或搭配目前專案上下文一起提問

### 重要規則

- `檔案預覽` 只是閱讀區，不會自動加入模型上下文
- 模型只會根據 **已同步釘選檔案** 來分析與回答
- 小到中型的 pinned code 組合，`Qwen 3.5` 會優先送完整檔案，不再只靠短節錄
- 若因 context 上限改用節錄模式，Web UI 會明確顯示這次不是完整檔案上下文
- 若上一版建議有錯，直接在同一個主對話框接著描述問題即可

---

## 6. Web UI 主要功能

### 專案路徑

- 用來選專案根目錄
- 點一下輸入框即可打開 Windows 原生資料夾選取視窗

### 模型

- 切換本次要使用的本地模型
- 切換後要重新 `開啟專案`

### 回應方式

- 主對話框與 `分析專案` 會直接保留較接近模型原始輸出的內容
- 系統不再對這兩條路徑做大幅回覆清洗或風格壓縮
- 模型仍然只會根據 **已同步釘選檔案** 回答

### 開啟專案

- 驗證路徑
- 準備 Git workspace
- 啟動本地模型
- 掃描檔案、入口與測試位置

### 專案摘要

- 顯示專案路徑、檔案數量、主要語言、可能入口與測試位置
- 也會顯示目前已同步的 pinned files

### 檔案樹

- 這裡是唯一的上下文選擇入口
- 勾選或取消勾選會立即同步釘選狀態

### 檔案預覽

- 僅供閱讀
- 幫你先確認單一檔案內容

### 對話

- 所有分析、解釋、修改建議與修正迭代都在主對話框內完成
- 若附加圖片但目前選定模型不支援圖片，Web UI 會明確提示改用支援圖片的模型，不再默默切換
- 圖片可用檔案上傳或直接貼上截圖
- 大型截圖在送入 `Qwen 3.5` 前會先自動縮圖，降低多模態 context 被圖片 token 吃滿的機率
- 聊天區會顯示本次 `context coverage`，讓你知道模型收到的是完整檔案還是節錄

---

## 7. CLI 使用方式

### 啟動本地模型

```cmd
scripts\start-server.cmd
```

切換模型：

```cmd
scripts\start-server.cmd gemma4
```

啟動 `Qwen 3.5`：

```cmd
scripts\start-server.cmd qwen35
```

### 啟動專案級對話

```cmd
scripts\code-chat.cmd C:\path\to\project
```

改用 Gemma 4：

```cmd
scripts\code-chat.cmd C:\path\to\project gemma4
```

改用 `Qwen 3.5`：

```cmd
scripts\code-chat.cmd C:\path\to\project qwen35
```

---

## 8. 常見使用情境

- 在無法上網的客戶端環境分析專案
- 在 air-gapped environment 中做 local LLM 專案理解
- 用 secure code analysis 方式理解交接專案
- 在 USB portable 工作流中帶著工具到不同 Windows 機器使用

---

## 9. 版本歷程

### V0.98b

- Web UI 與 README 版號同步更新為 `V0.98b`
- 將圖片附件的提示與 `上傳圖片` / `移除圖片` 控制整合到同一列，減少聊天表單占用高度
- `Qwen 3.5` 正式取代 `Qwen 2.5` 成為預設模型，Web UI 與 CLI 不再保留 `qwen` 作為正式選項
- 調整 `Qwen 3.5` 的 pinned file context 策略，小型 C# 專案分析會優先送完整檔案
- 新增 `context coverage` 顯示，若模型只收到節錄會明確提示
- 參考 Ollama API 的 `think`、圖片訊息與 completion 狀態概念，整理現有 `llama.cpp` 路線的 answer-only 與圖片能力判斷
- 新增大型截圖自動縮圖，減少 `Qwen 3.5` 在處理高解析圖片時出現 `failed to process image`
- README 補充新版預設約 `11.6 GB`、舊環境仍可能維持 `16.6 GB` 的容量差異，並說明這取決於本機是否還保留 `qwen25` 檔案

### V0.97b

- Web UI 與 README 版號同步更新為 `V0.97b`
- 修正 Qwen 與 Gemma4 在單一大型釘選檔案略超過上下文預算時只收到檔名的問題
- 主對話框與 `分析專案` 收斂為 raw-first prompt：保留必要的 `PINNED FILE CONTENT` 區塊，不自動把新增功能需求轉成修改建議
- 改善 Qwen 與 Gemma4 對新增 TCP/IP 連線規劃這類問題的回覆表現
- 將 Qwen 與 Gemma4 的 chat、analysis、edit suggestion 等待上限拉長，減少長回答被提早中斷
- 更新 GitHub README 截圖為 `V0.97b` 繁中 Qwen 與英文 Gemma4 實測畫面

### V0.96b

- Web UI 與 README 版號同步更新為 `V0.96b`
- 主對話框與 `分析專案` 收斂為較接近模型原始輸出的回應方式
- README 首頁與中英文說明同步更新目前模型定位與回應方式

### V0.95b

- 將當時 repo 內已完成的 `Gemma 4 E4B` 支援與穩定化調整收斂成正式版本
- 同步更新專案版號，作為後續雙語 README 與 UI 語言切換的基線版本
- 新增 README landing page 與中英文文件拆分
- Web UI 新增 `繁中 / EN` 完整語言切換

### V0.94b

- 移除 `修改建議` 的 modal / 獨立視窗
- 所有分析、建議、修正回合都回到主對話框
- 新增 `Gemma 4 E4B` 評估中模型

---

## 10. 重點提醒

- 預設模型已改為 `Qwen 3.5 9B Vision`
- `Gemma 4 E4B` 目前仍是第二模型，不是預設主力
- `Gemma 4 E4B` 在本專案目前仍以文字分析為主，不應直接把 Ollama Desktop 的圖片能力視為同等支援
- 新版預設下載組合約 `11.6 GB`，但舊版若三個模型都保留，本機工作區仍可能接近 `16.6 GB`
- 新版預設下載組合已不再包含 `Qwen 2.5`
- README 關鍵字已優化為：
  - offline AI
  - local LLM
  - USB portable
  - secure code analysis
  - air-gapped environment
  - privacy-first

### GitHub About 建議文案

- Description：`離線 Windows 本地 LLM 程式碼助理，提供 Qwen 3.5 圖文分析、釘選檔案上下文與隱私優先的專案理解。`
- Topics：`offline-ai`, `local-llm`, `windows`, `code-assistant`, `privacy-first`, `llama-cpp`

---

## 11. 已知限制

- 目前仍以 Windows 為主
- 第一次下載量大，需耐心等待
- `Gemma 4 E4B` 在 coding / structured edit 上仍弱於更大的模型與 `Qwen`

---

## 12. License

[MIT](LICENSE)
