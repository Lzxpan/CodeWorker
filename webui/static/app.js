const state = {
  uiState: "idle",
  projectPath: "",
  modelKey: "qwen",
  pinnedFiles: new Set(),
  history: [],
  currentTaskId: null,
  currentTaskKind: null,
  lastError: null,
};

const HELP_CONTENT = {
  "project-path": {
    title: "專案路徑",
    description: "這裡填要分析的專案資料夾。開啟專案時，CodeWorker 會以這個資料夾為根目錄建立 git 基線、掃描檔案並準備上下文。",
    usage: [
      "可直接貼上完整資料夾路徑。",
      "也可以按「選擇資料夾」用視窗點選。",
      "建議選真正的程式碼專案根目錄，不要選整個下載資料夾或大量影音資源資料夾。",
    ],
  },
  "pick-folder": {
    title: "選擇資料夾",
    description: "開啟 Windows 原生資料夾選取視窗，避免手動輸入路徑打錯。",
    usage: [
      "按下後選一個專案資料夾。",
      "選完會自動把路徑填回上方輸入框。",
      "若沒有跳出視窗，請確認沒有被其他視窗擋住。",
    ],
  },
  "model-key": {
    title: "模型",
    description: "選擇本次要用的本地模型。預設是 Qwen，比較適合中文對話與程式分析；Code Llama 是備援模型。",
    usage: [
      "一般建議使用 Qwen 2.5 Coder 7B。",
      "若要比對備援模型行為，再切換到 Code Llama 7B。",
      "切換模型後需重新開啟專案，系統才會改用新模型。",
    ],
  },
  "progress-panel": {
    title: "進度條",
    description: "顯示目前背景任務進行到哪個步驟。開專案時會依序經過路徑檢查、Git 準備、模型啟動、專案索引。",
    usage: [
      "百分比是目前任務進度。",
      "下面的文字會顯示當前步驟與補充訊息。",
      "如果長時間停在同一步，通常代表該步驟真的卡住或正在做較重的工作。",
    ],
  },
  "open-project": {
    title: "開啟專案",
    description: "把目前輸入的資料夾載入到 CodeWorker。這是使用其他功能前的必要步驟。",
    usage: [
      "第一次開專案時，系統會檢查 runtime、模型、git 狀態。",
      "若資料夾不是 git repo，系統會自動建立 `.git` 與基線快照。",
      "完成後，摘要、檔案樹、檔案預覽、分析與對話才會解鎖。",
    ],
  },
  "analyze-project": {
    title: "分析專案",
    description: "請模型先對整個專案做總覽分析，通常會整理入口、核心模組、設定檔與測試位置。",
    usage: [
      "適合第一次接觸專案時先按一次。",
      "分析結果會出現在右側對話區。",
      "若尚未開啟專案，這個按鈕會被停用。",
    ],
  },
  "error-panel": {
    title: "錯誤訊息",
    description: "當下載、模型啟動、專案開啟或對話發生問題時，這裡會顯示錯誤碼、摘要與詳細內容。",
    usage: [
      "先看錯誤碼與摘要，再看詳細內容。",
      "若有 log 路徑，可用來進一步除錯。",
      "有些錯誤會附帶可執行動作，例如重新下載模型。",
    ],
  },
  "redownload-model": {
    title: "重新下載模型",
    description: "當模型檔損壞、下載不完整或讀取失敗時，用這個功能重新抓指定模型。",
    usage: [
      "按下後會在背景重新下載模型。",
      "下載進度會顯示在進度條中。",
      "下載完成後，再按一次「開啟專案」。",
    ],
  },
  "dismiss-error": {
    title: "關閉錯誤",
    description: "先把目前的錯誤卡收起來，不會刪除任何資料或修正問題。",
    usage: [
      "只會隱藏錯誤顯示。",
      "若問題尚未解決，之後再次操作時仍可能重新出現。",
    ],
  },
  "project-summary": {
    title: "專案摘要",
    description: "用來快速看整個專案的大方向。它不是原始碼本身，而是系統掃描後整理出的重點資訊。",
    usage: [
      "可看到專案路徑、已掃描檔案數量、估計文字檔大小、主要語言、可能入口檔案與測試位置。",
      "適合先用來判斷這個資料夾是不是你真正要分析的專案。",
      "若摘要內容不對，通常代表你選錯資料夾，或專案裡混入太多非程式碼內容。",
    ],
  },
  "refresh-status": {
    title: "重新整理",
    description: "重新抓一次目前載入中的專案狀態與畫面內容。",
    usage: [
      "適合在專案已開啟後，重新同步摘要、檔案樹與對話歷史。",
      "不會重新下載模型，也不會自動重跑分析。",
    ],
  },
  "file-tree": {
    title: "檔案樹",
    description: "顯示目前已掃描到的檔案清單。這裡是你選擇上下文檔案的地方。",
    usage: [
      "點檔名可在上方「檔案預覽」查看內容。",
      "左邊勾選框可把檔案加入釘選清單。",
      "按「套用釘選」後，這些檔案會優先放進之後的分析與對話上下文。",
    ],
  },
  "apply-pins": {
    title: "套用釘選",
    description: "把你在檔案樹中勾選的檔案設成優先上下文。",
    usage: [
      "先在檔案樹勾選想關注的檔案。",
      "按下後，模型之後分析與對話會優先引用這些檔案。",
      "適合只想聚焦某幾個模組時使用。",
    ],
  },
  "file-preview": {
    title: "檔案預覽",
    description: "顯示你在檔案樹點到的單一檔案內容節錄，讓你先快速確認內容再決定是否要納入對話上下文。",
    usage: [
      "它是閱讀區，不是編輯器。",
      "點檔案樹中的任一檔案，內容就會顯示在這裡。",
      "若內容很長，這個區塊本身可以捲動，不會把整頁拉長。",
    ],
  },
  "chat-panel": {
    title: "對話",
    description: "你和本地模型互動的主區域。分析結果與一般提問都會顯示在這裡。",
    usage: [
      "先開啟專案，再開始提問。",
      "對話內容過長時，這個區塊本身會出現捲動條，不會延伸整頁。",
      "適合詢問架構、模組責任、bug 線索、修改建議等問題。",
    ],
  },
  "chat-input": {
    title: "對話輸入",
    description: "輸入你要問模型的內容。它會結合目前的專案摘要、檔案樹與釘選檔案回答。",
    usage: [
      "可直接問：『登入流程在哪些檔案？』",
      "也可下指令：『先不要改檔，先分析 bug 可能位置。』",
      "若想聚焦特定模組，建議先在檔案樹勾選後再提問。",
    ],
  },
  "send-chat": {
    title: "送出",
    description: "把目前輸入框的問題送到模型。",
    usage: [
      "送出前請確認已開啟專案。",
      "送出後回答會顯示在對話區。",
      "如果目前正在開專案或下載模型，這個按鈕會被停用。",
    ],
  },
  "clear-chat": {
    title: "清空對話",
    description: "清掉目前頁面上的對話歷史，讓你重新開始一輪提問。",
    usage: [
      "只清除這次 web UI 的對話內容。",
      "不會刪除專案、模型、摘要或檔案樹。",
    ],
  },
};

const elements = {
  projectPath: document.getElementById("projectPath"),
  modelKey: document.getElementById("modelKey"),
  pickFolderBtn: document.getElementById("pickFolderBtn"),
  openProjectBtn: document.getElementById("openProjectBtn"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  refreshStatusBtn: document.getElementById("refreshStatusBtn"),
  applyPinsBtn: document.getElementById("applyPinsBtn"),
  projectSummary: document.getElementById("projectSummary"),
  fileTree: document.getElementById("fileTree"),
  previewPath: document.getElementById("previewPath"),
  filePreview: document.getElementById("filePreview"),
  chatLog: document.getElementById("chatLog"),
  chatForm: document.getElementById("chatForm"),
  chatInput: document.getElementById("chatInput"),
  sendChatBtn: document.getElementById("sendChatBtn"),
  clearChatBtn: document.getElementById("clearChatBtn"),
  statusBadge: document.getElementById("statusBadge"),
  treeItemTemplate: document.getElementById("treeItemTemplate"),
  progressPanel: document.getElementById("progressPanel"),
  progressTitle: document.getElementById("progressTitle"),
  progressPercent: document.getElementById("progressPercent"),
  progressBar: document.getElementById("progressBar"),
  progressStep: document.getElementById("progressStep"),
  errorPanel: document.getElementById("errorPanel"),
  errorCode: document.getElementById("errorCode"),
  errorMessage: document.getElementById("errorMessage"),
  errorDetails: document.getElementById("errorDetails"),
  errorMeta: document.getElementById("errorMeta"),
  errorActionBtn: document.getElementById("errorActionBtn"),
  dismissErrorBtn: document.getElementById("dismissErrorBtn"),
  helpModal: document.getElementById("helpModal"),
  helpTitle: document.getElementById("helpTitle"),
  helpBody: document.getElementById("helpBody"),
  closeHelpBtn: document.getElementById("closeHelpBtn"),
};

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!payload.ok) {
    throw payload.error || { code: "REQUEST_FAILED", message: "Request failed.", details: "" };
  }
  return payload.data;
}

function normalizeError(error, fallbackCode = "REQUEST_FAILED", fallbackMessage = "Request failed.") {
  if (error && typeof error === "object" && "message" in error) {
    return {
      code: error.code || fallbackCode,
      message: error.message || fallbackMessage,
      details: error.details || "",
      action: error.action,
      logPath: error.logPath,
      modelKey: error.modelKey,
    };
  }
  return { code: fallbackCode, message: fallbackMessage, details: String(error || "") };
}

function setStatus(text, busy = false) {
  elements.statusBadge.textContent = text;
  elements.statusBadge.dataset.busy = busy ? "1" : "0";
}

function setUiState(nextState) {
  state.uiState = nextState;
  const ready = nextState === "ready";
  const opening = nextState === "opening";
  const busy = opening || state.currentTaskKind === "redownload-model";

  elements.openProjectBtn.disabled = opening;
  elements.pickFolderBtn.disabled = opening;
  elements.modelKey.disabled = opening;
  elements.projectPath.disabled = opening;
  elements.analyzeBtn.disabled = !ready || busy;
  elements.applyPinsBtn.disabled = !ready || busy;
  elements.sendChatBtn.disabled = !ready || busy;
  elements.chatInput.disabled = !ready || busy;
  elements.clearChatBtn.disabled = !ready;
}

function renderProgress(progress = 0, step = "", title = "背景作業執行中") {
  if (state.uiState === "opening" || state.currentTaskKind === "redownload-model") {
    elements.progressPanel.classList.remove("hidden");
  } else {
    elements.progressPanel.classList.add("hidden");
  }
  elements.progressTitle.textContent = title;
  elements.progressPercent.textContent = `${progress}%`;
  elements.progressBar.style.width = `${progress}%`;
  elements.progressStep.textContent = step || "等待中";
}

function renderHelpContent(entry) {
  const sections = [`<p>${escapeHtml(entry.description || "")}</p>`];
  if (entry.usage?.length) {
    sections.push("<h3>使用方式</h3>");
    sections.push(`<ul>${entry.usage.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (entry.notes?.length) {
    sections.push("<h3>補充說明</h3>");
    sections.push(`<ul>${entry.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  return sections.join("");
}

function openHelp(helpKey) {
  const entry = HELP_CONTENT[helpKey];
  if (!entry) return;
  elements.helpTitle.textContent = entry.title;
  elements.helpBody.innerHTML = renderHelpContent(entry);
  elements.helpModal.classList.remove("hidden");
  elements.helpModal.setAttribute("aria-hidden", "false");
}

function closeHelp() {
  elements.helpModal.classList.add("hidden");
  elements.helpModal.setAttribute("aria-hidden", "true");
}

function buildProgressLabel(task) {
  if (task.message && task.step && task.message !== task.step) {
    return `${task.step} · ${task.message}`;
  }
  return task.message || task.step || "等待中";
}

function showError(error) {
  state.lastError = error;
  elements.errorPanel.classList.remove("hidden");
  elements.errorCode.textContent = error.code || "";
  elements.errorMessage.textContent = error.message || "發生未預期錯誤。";
  elements.errorDetails.textContent = error.details || "";
  const meta = [];
  if (error.logPath) meta.push(`Log: ${error.logPath}`);
  if (error.modelKey) meta.push(`Model: ${error.modelKey}`);
  elements.errorMeta.textContent = meta.join(" | ");
  if (error.action === "redownload-model") {
    elements.errorActionBtn.classList.remove("hidden");
  } else {
    elements.errorActionBtn.classList.add("hidden");
  }
}

function clearError() {
  state.lastError = null;
  elements.errorPanel.classList.add("hidden");
  elements.errorCode.textContent = "";
  elements.errorMessage.textContent = "";
  elements.errorDetails.textContent = "";
  elements.errorMeta.textContent = "";
  elements.errorActionBtn.classList.add("hidden");
}

function appendMessage(role, content) {
  const item = document.createElement("div");
  item.className = `chat-item ${role}`;
  item.innerHTML = `
    <div class="chat-role">${role === "user" ? "你" : "Assistant"}</div>
    <div class="chat-content">${escapeHtml(content)}</div>
  `;
  elements.chatLog.appendChild(item);
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function renderHistory(history) {
  elements.chatLog.innerHTML = "";
  history.forEach((item) => appendMessage(item.role, item.content));
}

function renderTree(tree) {
  elements.fileTree.innerHTML = "";
  if (!tree.length) {
    elements.fileTree.classList.add("empty");
    elements.fileTree.textContent = "尚未載入檔案。";
    return;
  }
  elements.fileTree.classList.remove("empty");
  tree.forEach((path) => {
    const node = elements.treeItemTemplate.content.firstElementChild.cloneNode(true);
    const checkbox = node.querySelector(".pin-checkbox");
    const button = node.querySelector(".tree-link");
    checkbox.checked = state.pinnedFiles.has(path);
    checkbox.disabled = state.uiState !== "ready";
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.pinnedFiles.add(path);
      else state.pinnedFiles.delete(path);
    });
    button.textContent = path;
    button.disabled = state.uiState !== "ready";
    button.addEventListener("click", () => loadFilePreview(path));
    elements.fileTree.appendChild(node);
  });
}

async function refreshStatus() {
  const data = await requestJson("/api/status");
  state.projectPath = data.projectPath || "";
  state.modelKey = data.modelKey || "qwen";
  state.pinnedFiles = new Set(data.pinnedFiles || []);
  state.history = data.history || [];
  elements.projectPath.value = state.projectPath;
  elements.modelKey.value = state.modelKey;
  elements.projectSummary.textContent = data.summary || "尚未開啟專案。";
  renderTree(data.tree || []);
  renderHistory(state.history);
  if (state.uiState !== "opening" && state.currentTaskKind !== "redownload-model") {
    setUiState(data.uiState || (data.projectPath ? "ready" : "idle"));
    if (data.projectPath) {
      setStatus("專案已就緒");
      elements.filePreview.textContent = elements.filePreview.textContent || "專案已開啟。";
    } else {
      setStatus("待命");
    }
  }
}

function resetProjectViews(message = "尚未開啟專案。") {
  elements.projectSummary.textContent = message;
  elements.previewPath.textContent = "未選擇檔案";
  elements.filePreview.textContent = "點左側檔案即可預覽內容，並可勾選釘選到對話上下文。";
  renderTree([]);
}

async function pickFolder() {
  clearError();
  setStatus("開啟資料夾選取視窗", true);
  try {
    const data = await requestJson("/api/pick-folder", {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (!data.canceled && data.path) {
      elements.projectPath.value = data.path;
    }
    setStatus(state.uiState === "ready" ? "專案已就緒" : "待命");
  } catch (error) {
    setStatus("選擇資料夾失敗");
    showError(normalizeError(error, "PICK_FOLDER_FAILED", "選擇資料夾失敗。"));
  }
}

async function pollTask(taskId, kind) {
  state.currentTaskId = taskId;
  state.currentTaskKind = kind;
  const title = kind === "redownload-model" ? "正在重新下載模型" : "正在開啟專案";

  while (true) {
    const task = await requestJson(`/api/tasks/${taskId}`);
    renderProgress(task.progress || 0, buildProgressLabel(task), title);

    if (task.status === "completed") {
      state.currentTaskId = null;
      state.currentTaskKind = null;
      if (kind === "open-project") {
        clearError();
        setUiState("ready");
        await refreshStatus();
        setStatus("專案已就緒");
        elements.filePreview.textContent = "專案已開啟。你可以先按「分析專案」，或直接開始提問。";
      } else {
        setUiState(state.projectPath ? "error" : "idle");
        setStatus("模型已重新下載");
        showError({
          code: "MODEL_READY",
          message: "模型已重新下載完成。",
          details: "請再次按「開啟專案」重新啟動模型與索引流程。",
          modelKey: task.result?.modelKey,
        });
      }
      renderProgress(0, "", title);
      return;
    }

    if (task.status === "failed") {
      state.currentTaskId = null;
      state.currentTaskKind = null;
      setUiState("error");
      setStatus(kind === "redownload-model" ? "模型重新下載失敗" : "開啟失敗");
      showError(task.error || { code: "TASK_FAILED", message: "Task failed.", details: "" });
      renderProgress(task.progress || 100, buildProgressLabel(task), title);
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

async function openProject() {
  const projectPath = elements.projectPath.value.trim();
  const modelKey = elements.modelKey.value;
  if (!projectPath) {
    showError({ code: "PROJECT_PATH_INVALID", message: "請先選擇專案資料夾。", details: "" });
    return;
  }

  clearError();
  resetProjectViews("正在開啟專案，請稍候...");
  elements.chatLog.innerHTML = "";
  setUiState("opening");
  setStatus("正在開啟專案", true);
  renderProgress(0, "建立背景任務", "正在開啟專案");

  try {
    const data = await requestJson("/api/tasks/open-project", {
      method: "POST",
      body: JSON.stringify({ projectPath, modelKey }),
    });
    state.projectPath = projectPath;
    state.modelKey = modelKey;
    await pollTask(data.taskId, "open-project");
  } catch (error) {
    setUiState("error");
    setStatus("開啟失敗");
    showError(normalizeError(error, "OPEN_PROJECT_FAILED", "開啟專案失敗。"));
  }
}

async function redownloadModel() {
  const modelKey = state.lastError?.modelKey || elements.modelKey.value || "qwen";
  clearError();
  setUiState("error");
  setStatus("正在重新下載模型", true);
  renderProgress(0, "建立背景任務", "正在重新下載模型");
  try {
    const data = await requestJson("/api/models/redownload", {
      method: "POST",
      body: JSON.stringify({ modelKey }),
    });
    await pollTask(data.taskId, "redownload-model");
  } catch (error) {
    setStatus("模型重新下載失敗");
    showError(normalizeError(error, "MODEL_DOWNLOAD_FAILED", "模型重新下載失敗。"));
  }
}

async function analyzeProject() {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: "請先完成開啟專案。", details: "" });
    return;
  }
  clearError();
  setStatus("正在分析", true);
  try {
    const data = await requestJson("/api/analyze", {
      method: "POST",
      body: JSON.stringify({}),
    });
    appendMessage("assistant", data.reply);
    setStatus("分析完成");
  } catch (error) {
    setStatus("分析失敗");
    showError(normalizeError(error, "ANALYZE_FAILED", "分析失敗。"));
  }
}

async function loadFilePreview(path) {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: "請先完成開啟專案。", details: "" });
    return;
  }
  elements.previewPath.textContent = path;
  elements.filePreview.textContent = "讀取中...";
  try {
    const data = await requestJson(`/api/file?path=${encodeURIComponent(path)}`);
    elements.filePreview.textContent = data.content;
  } catch (error) {
    elements.filePreview.textContent = "";
    showError(normalizeError(error, "FILE_PREVIEW_FAILED", "檔案預覽失敗。"));
  }
}

async function applyPins() {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: "請先完成開啟專案。", details: "" });
    return;
  }
  clearError();
  setStatus("更新上下文", true);
  try {
    await requestJson("/api/pin-files", {
      method: "POST",
      body: JSON.stringify({ files: [...state.pinnedFiles] }),
    });
    setStatus("已更新上下文");
  } catch (error) {
    setStatus("更新失敗");
    showError(normalizeError(error, "PIN_FILES_FAILED", "更新上下文失敗。"));
  }
}

async function sendChat(event) {
  event.preventDefault();
  const message = elements.chatInput.value.trim();
  if (!message) return;
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: "請先完成開啟專案。", details: "" });
    return;
  }
  clearError();
  appendMessage("user", message);
  elements.chatInput.value = "";
  setStatus("正在思考", true);
  try {
    const data = await requestJson("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    appendMessage("assistant", data.reply);
    setStatus("完成");
  } catch (error) {
    setStatus("對話失敗");
    const normalized = normalizeError(error, "CHAT_FAILED", "對話失敗。");
    showError(normalized);
    appendMessage("assistant", `發生錯誤：${normalized.message}`);
  }
}

function clearChat() {
  requestJson("/api/reset-history", {
    method: "POST",
    body: JSON.stringify({}),
  })
    .then(() => {
      elements.chatLog.innerHTML = "";
      setStatus(state.uiState === "ready" ? "專案已就緒" : "對話已清空");
    })
    .catch((error) => showError(normalizeError(error, "RESET_HISTORY_FAILED", "清空對話失敗。")));
}

document.querySelectorAll(".help-trigger").forEach((button) => {
  button.addEventListener("click", () => openHelp(button.dataset.help));
});

elements.pickFolderBtn.addEventListener("click", pickFolder);
elements.openProjectBtn.addEventListener("click", openProject);
elements.analyzeBtn.addEventListener("click", analyzeProject);
elements.refreshStatusBtn.addEventListener("click", refreshStatus);
elements.applyPinsBtn.addEventListener("click", applyPins);
elements.chatForm.addEventListener("submit", sendChat);
elements.clearChatBtn.addEventListener("click", clearChat);
elements.errorActionBtn.addEventListener("click", redownloadModel);
elements.dismissErrorBtn.addEventListener("click", clearError);
elements.closeHelpBtn.addEventListener("click", closeHelp);
elements.helpModal.addEventListener("click", (event) => {
  if (event.target === elements.helpModal) closeHelp();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !elements.helpModal.classList.contains("hidden")) {
    closeHelp();
  }
});

setUiState("idle");
refreshStatus()
  .then(() => setUiState(state.projectPath ? "ready" : "idle"))
  .catch(() => {
    setUiState("idle");
    setStatus("待命");
  });
