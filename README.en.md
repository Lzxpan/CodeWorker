# CodeWorker V0.98b

> A privacy-first, offline AI code assistant for Windows, built for local LLM workflows and USB portable deployment.

[繁體中文](README.zh-TW.md) | [Landing page](README.md)

`CodeWorker` packages `llama.cpp`, `WinPython`, `PortableGit`, GGUF models, and a local Web UI into a portable workspace. It is designed for:

- **offline AI**
- **local LLM**
- **USB portable**
- **secure code analysis**
- **on-premise**
- **air-gapped environment**
- **privacy-first** development

---

## 1. System Requirements

- Windows 10 / 11 x64
- 32GB RAM is the more reliable target for larger local models
- If the machine uses integrated graphics, shared memory can reduce the system RAM actually available to the model
- Whether the machine is sufficient still depends on the user's real hardware and runtime load
- AVX2-capable CPU recommended
- Internet access is required for the first runtime / model download
- The initial download is **over 5GB**, so expect some waiting time depending on network speed and USB / disk write speed
- The new default two-model layout is roughly **11.6 GB** after removing `Qwen 2.5` from the packaged route
- Older upgraded workspaces that still keep the removed `qwen25` model files can remain near the previous **16.6 GB** footprint
- Reclaiming that space still requires deleting the old local `qwen2.5` model directory
- After setup completes, the tool can run offline

---

## 2. Model Positioning

- `Qwen 3.5 9B Vision`
  - default and primary model
  - handles both text and image input
  - now used as the main code-analysis and project-chat model
- `Gemma 4 E4B`
  - secondary optional model
  - validated for the `llama.cpp + GGUF + Windows local + USB` architecture
  - currently treated as a text-analysis model in this project; image input is not yet a formally supported path in the current local `llama.cpp` GGUF route
  - can start and localize target code regions, but is still less stable than `Qwen 3.5` for edit suggestions

---

## 3. Installation

### Full bootstrap

```cmd
scripts\bootstrap.cmd
```

This prepares:

- `llama.cpp`
- `PortableGit`
- `WinPython`
- default model files

### Optional CLI agent setup

```cmd
scripts\install-aider.cmd
```

---

## 4. Quick Start

### Launch the Web UI

```cmd
scripts\launch-webui.cmd
```

Then open:

```text
http://127.0.0.1:8764
```

### Web UI screenshots

![CodeWorker V0.98b English Web UI overview](docs/screenshots/webui-overview-en-v097b.png)

---

## 5. Web UI Workflow

1. Click the project path field and choose the project root
2. Confirm the model selection
3. Click `Open project`
4. Check the files you want in the file tree
5. The pin state syncs immediately when you check or uncheck files
6. Ask questions or describe change requests in the main chat

For image understanding:

7. Click `Attach image`, or paste a screenshot into the chat box
8. Make sure the currently selected model actually supports images; the formally supported image model in this build is `Qwen 3.5 9B Vision`
9. Ask about the image alone, or combine it with the current project context

### Important context rules

- `File preview` is read-only and **does not** automatically become model context
- The model only answers from the **synced pinned files**
- Small to medium pinned code sets are sent to `Qwen 3.5` as full files whenever the local context budget allows it
- If the request falls back to excerpt mode, the Web UI now clearly says the model only received excerpts
- If the last suggestion is wrong, continue in the same main chat and explain what is wrong

---

## 6. Main Web UI Features

### Project path

- Chooses the project root
- Clicking the input opens the native Windows folder picker

### Model

- Switches the local model for the current session
- Reopen the project after changing the model

### Response behavior

- Main chat and `Analyze project` now stay closer to the model's original output
- The system no longer applies heavy reply cleanup or style compression
- Answers still use only the **synced pinned files** as trusted context

### Open project

- validates the path
- prepares the Git workspace
- starts the local model
- scans files, entry points, and test locations

### Project summary

- shows project path, file count, major languages, likely entry points, and test locations
- also shows the currently synced pinned files

### File tree

- the only place where model context is selected
- checking or unchecking files syncs the pinned state immediately

### File preview

- read-only preview
- helps you inspect a single file before deciding whether to pin it

### Chat

- all analysis, explanation, and iterative code-suggestion work happens in the main chat panel
- if an image is attached while the selected model does not support image input, the Web UI now shows a clear error instead of silently switching models
- images can be added either by file upload or by pasting a screenshot
- larger screenshots are automatically downscaled before they are sent to `Qwen 3.5`, reducing the chance that image tokens consume too much multimodal context
- the chat panel shows `context coverage` so you can tell whether the model received full files or excerpts

---

## 7. CLI Usage

### Start the local model server

```cmd
scripts\start-server.cmd
```

Switch model:

```cmd
scripts\start-server.cmd gemma4
```

Start `Qwen 3.5`:

```cmd
scripts\start-server.cmd qwen35
```

### Start project-level chat

```cmd
scripts\code-chat.cmd C:\path\to\project
```

Use Gemma 4:

```cmd
scripts\code-chat.cmd C:\path\to\project gemma4
```

Use `Qwen 3.5`:

```cmd
scripts\code-chat.cmd C:\path\to\project qwen35
```

---

## 8. Typical Use Cases

- understanding a codebase in an offline or air-gapped environment
- secure code analysis where source code cannot leave the machine
- carrying a USB portable AI assistant to multiple Windows machines
- evaluating `Qwen` and `Gemma 4 E4B` side by side on the same pinned files

---

## 9. Version History

### V0.98b

- updated the Web UI and README version strings to `V0.98b`
- moved the image-attachment hint and `Attach image` / `Remove image` controls into the same row to reduce chat form height
- replaced `Qwen 2.5` with `Qwen 3.5` as the default model in the Web UI and CLI
- expanded the `Qwen 3.5` pinned-file context budget so small C# project analysis can use full files instead of short excerpts
- added `context coverage` so excerpt-mode requests are visible in the UI
- aligned the current `llama.cpp` request flow with Ollama-style concepts such as answer-only output, image-capable model checks, and explicit completion-state handling
- added automatic screenshot downscaling to reduce `failed to process image` errors on larger `Qwen 3.5` image inputs
- updated the storage note to distinguish the new default footprint of about `11.6 GB` from older upgraded machines that may still stay near `16.6 GB` until `qwen25` files are deleted

### V0.97b

- updated the Web UI and README version strings to `V0.97b`
- fixed a Qwen and Gemma4 pinned-file context issue where a single large pinned file could degrade to filename-only context
- aligned main chat and `Analyze project` with a raw-first prompt flow: keep the required `PINNED FILE CONTENT` blocks, but do not auto-route feature requests into edit plans
- improved Qwen and Gemma4 responses for feature-planning questions such as adding TCP/IP connectivity
- extended Qwen and Gemma4 chat, analysis, and edit suggestion timeouts to reduce early interruption of long responses
- updated the GitHub README screenshots with `V0.97b` Traditional Chinese Qwen and English Gemma4 smoke-test views

### V0.96b

- updated the Web UI and README version strings to `V0.96b`
- aligned main chat and `Analyze project` with a response flow closer to the models' original output
- synchronized the landing page and bilingual docs with the current model positioning and response behavior

### V0.95b

- promoted the repo state at that time to a formal `V0.95b` baseline
- added the README landing page plus split `README.zh-TW.md` and `README.en.md`
- added a full `繁中 / EN` language switch to the Web UI

### V0.94b

- removed the edit-plan modal
- moved all analysis and suggestion iterations back into the main chat
- added `Gemma 4 E4B` as an evaluation model

---

## 10. Important Notes

- `Qwen 3.5 9B Vision` is now the default model
- `Gemma 4 E4B` remains the secondary model, not the primary default
- `Gemma 4 E4B` should still be treated as a text model in this project unless the local `llama.cpp` GGUF route is separately verified for image input
- The new default packaged layout is about `11.6 GB`, but upgraded workspaces can still remain near the old `16.6 GB` footprint if `qwen25` files are still present

---

## 11. Known Limitations

- Windows-first workflow
- large first-time download size
- `Gemma 4 E4B` is still weaker than `Qwen` for structured code-edit suggestions

---

## 12. License

[MIT](LICENSE)
