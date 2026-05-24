# Qwen3.6-35B-A3B CPU-only llama.cpp 設定

本文位置：

- 本檔案：`docs\qwen36a3b-cpu-only-llamacpp.md`
- README 摘要：`README.md` / `README.zh-TW.md` 的「Qwen3.6-35B-A3B CPU-only llama.cpp 設定」
- 英文摘要：`README.en.md` 的「Qwen3.6-35B-A3B CPU-only llama.cpp Settings」

## 適用情境

`Qwen3.6-35B-A3B Vision` 可以在沒有獨立顯卡、顯存不足，或你想完全關閉 GPU offload 時用 CPU-only 模式啟動。

這不是 8GB NVIDIA 最佳化模式。CPU-only 會更慢，也更依賴 system RAM。建議至少 `64GB RAM`，先用 `16k` 或 `32k` context 測試，穩定後再提高。

## CodeWorker 自動啟動方式

在 Web UI 選擇 `Qwen3.6-35B-A3B Vision` 後啟動模型。若目前硬體沒有 NVIDIA GPU 或 VRAM 很低，CodeWorker 的硬體設定會走低顯存 / CPU-oriented profile，核心行為是：

- `MODEL_N_GPU_LAYERS=0`
- `MODEL_CONTEXT_WINDOW` 依硬體降到較保守值
- `MODEL_BATCH_SIZE=256`
- `MODEL_UBATCH_SIZE=64`
- 保留 `--n-cpu-moe=999`

可用下列命令確認 CodeWorker 會傳給 `llama.cpp` 的環境變數：

```cmd
runtime\WinPython\python\python.exe scripts\resolve_model_env.py qwen36a3b
```

如果輸出中看到 `MODEL_N_GPU_LAYERS=0`，代表 CodeWorker 會以不 offload layers 到 GPU 的方式啟動。

## 手動 llama.cpp CPU-only 命令

如果你要不透過 Web UI，直接手動啟動 `llama-server`，可用以下命令：

```cmd
runtime\llama.cpp\llama-server.exe ^
  -m models\qwen3.6-35b-a3b-ud-q4-k-m\Qwen3.6-35B-A3B-UD-Q4_K_M.gguf ^
  --mmproj models\qwen3.6-35b-a3b-ud-q4-k-m\mmproj-BF16.gguf ^
  --host 127.0.0.1 ^
  --port 8087 ^
  --ctx-size 32768 ^
  --cache-type-k q4_0 ^
  --cache-type-v q4_0 ^
  --threads 12 ^
  --n-gpu-layers 0 ^
  --n-cpu-moe 999 ^
  --batch-size 256 ^
  --ubatch-size 64 ^
  --jinja
```

純文字或程式碼用途可以先拿掉 `--mmproj`，降低啟動與記憶體壓力：

```cmd
runtime\llama.cpp\llama-server.exe ^
  -m models\qwen3.6-35b-a3b-ud-q4-k-m\Qwen3.6-35B-A3B-UD-Q4_K_M.gguf ^
  --host 127.0.0.1 ^
  --port 8087 ^
  --ctx-size 32768 ^
  --cache-type-k q4_0 ^
  --cache-type-v q4_0 ^
  --threads 12 ^
  --n-gpu-layers 0 ^
  --n-cpu-moe 999 ^
  --batch-size 256 ^
  --ubatch-size 64 ^
  --jinja
```

## 參數說明

- `--n-gpu-layers 0`：明確禁止 GPU offload，避免沒有顯卡或顯存不足時仍嘗試把 layers 放進 GPU。
- `--n-cpu-moe=999`：MoE layers 保留在 CPU/RAM；CPU-only 時搭配 `--n-gpu-layers 0` 可避免 MoE offload 誤判。
- `--ctx-size 32768`：先用 `32k`；RAM 不足時降到 `16384` 或 `8192`。
- `--cache-type-k q4_0 --cache-type-v q4_0`：降低 KV cache 記憶體需求。
- `--batch-size 256 --ubatch-size 64`：比 8GB NVIDIA profile 更保守，適合 CPU-only 測試。
- `--mmproj`：只有需要圖片理解時才保留；純文字 / 程式碼修改可先省略。
- `--jinja`：啟用模型 chat template；Qwen 系列建議保留。
- 不建議 CPU-only 預設加 `--mlock`；除非 RAM 很充足，否則可能讓 Windows 更難回收記憶體。

## 常見調整

RAM 不足或啟動失敗：

```cmd
--ctx-size 16384
```

仍失敗時：

```cmd
--ctx-size 8192
```

CPU thread 太高導致系統卡頓時，降低 `--threads`：

```cmd
--threads 8
```

只做程式碼修改、不看圖片時，先拿掉：

```cmd
--mmproj models\qwen3.6-35b-a3b-ud-q4-k-m\mmproj-BF16.gguf
```

## 排錯位置

CodeWorker 自動啟動時，優先看：

- `logs\llama-server-qwen36a3b-*.err.log`
- `logs\llama-server-qwen36a3b-*.log`
- `logs\hardware-optimization.jsonl`

手動啟動時，先確認：

- `models\qwen3.6-35b-a3b-ud-q4-k-m\Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` 是否存在。
- 若需要圖片理解，`models\qwen3.6-35b-a3b-ud-q4-k-m\mmproj-BF16.gguf` 是否存在。
- `runtime\llama.cpp\llama-server.exe` 是否存在。
- `--ctx-size` 是否過大導致記憶體不足。

## 注意事項

- `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` 是 21GB 等級模型，CPU-only 對 RAM 壓力很高。
- CPU-only 推理延遲會明顯高於 CUDA / Vulkan offload；產生修改計畫時要允許較長時間。
- 如果 Windows 開始大量 paging，先降低 `--ctx-size`，再降低 `--threads` 或拿掉 `--mmproj`。
- Context 越大，KV cache 越大；能載入模型不代表能穩定跑大 context。
