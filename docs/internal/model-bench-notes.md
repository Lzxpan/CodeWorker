# Model Bench Notes

這份文件用來說明 `CodeWorker` 目前保留的三個模型 bench 檔案用途，方便後續交接與重跑測試時快速定位。

## 1. `scripts/measure_context_limits.py`

用途：

- 啟動本機模型並測量實際可用的 `context / tokens` 上限
- 驗證 `llama-server` 是否可成功啟動
- 驗證 `/v1/models` 與 `chat completion` 是否能在指定 context 下正常工作
- 比較一般問答、長分析與簡單結構化輸出在不同模型上的穩定度

定位：

- 這是**內部測試腳本**
- 不屬於一般使用者工作流程
- 重跑 bench 時應優先從這個檔案開始

## 2. `logs/model-context-bench.json`

用途：

- 保存 bench 的完整原始資料
- 記錄每個模型、每個 context 設定下的測試結果
- 適合後續程式化比對、回歸驗證或重新整理成摘要

內容通常包含：

- 啟動是否成功
- 使用的 port 與 context
- 每個測試項目的 `ok / error / finish_reason / length`
- timeout、空回覆、context overflow 等失敗訊息

定位：

- 這是**機器可讀的原始紀錄**
- 若摘要與實際結果有出入，應以這份 JSON 為準

## 3. `logs/model-context-summary.md`

用途：

- 將 `model-context-bench.json` 的結果整理成人類可快速閱讀的摘要
- 方便直接查看：
  - 哪個模型在這台機器上最穩定
  - 每個模型實際可用到哪個 context
  - 哪些模型在高 context 下會失敗

定位：

- 這是**交接與快速閱讀用摘要**
- 給維護者先看結論，再視需要回查 JSON 與腳本

## 使用建議

若未來要重新評估模型：

1. 先看 `logs/model-context-summary.md`
2. 若要確認細節，再看 `logs/model-context-bench.json`
3. 若要重新量測或修改測試題組，再編修 `scripts/measure_context_limits.py`

## 注意事項

- 這三個檔案屬於**內部測試資料**
- 不建議把 bench 結論直接放進公開 README
- 若重新跑 bench，應說明：
  - 使用的模型版本
  - 量化版本
  - context 設定
  - 測試題組是否有變更
