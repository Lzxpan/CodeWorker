const state = {
  uiState: "idle",
  projectPath: "",
  modelKey: "qwen",
  pinnedFiles: new Set(),
  currentPreviewPath: null,
  pendingEdit: null,
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
      "直接點一下路徑框，就會開啟 Windows 原生資料夾選取視窗。",
      "選完後，路徑會自動填回輸入框。",
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
    description: "請模型根據目前已套用的釘選檔案做總覽分析，通常會整理入口、核心模組、設定檔與測試位置。",
    usage: [
      "先在檔案樹勾選要分析的檔案，再按「套用釘選」。",
      "分析結果會出現在右側對話區。",
      "若尚未開啟專案或尚未套用釘選檔案，系統會提示你先完成這一步。",
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
      "也會顯示目前已套用的釘選檔案清單，方便確認模型此刻會看哪些檔案。",
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
    description: "顯示目前已掃描到的檔案清單。這裡是你選擇模型上下文檔案的唯一入口。",
    usage: [
      "點檔名可在上方「檔案預覽」查看內容。",
      "左邊勾選框可把檔案加入釘選清單。",
      "按「套用釘選」後，這些檔案才會真正加入之後的分析、對話與修改建議上下文。",
    ],
  },
  "apply-pins": {
    title: "套用釘選",
    description: "把你在檔案樹中勾選的檔案設成目前唯一的模型上下文。",
    usage: [
      "先在檔案樹勾選想關注的檔案。",
      "按下後，模型之後分析、對話與修改建議只會根據這些檔案回答。",
      "適合只想聚焦某幾個模組時使用。",
    ],
  },
  "file-preview": {
    title: "檔案預覽",
    description: "顯示你在檔案樹點到的單一檔案內容，讓你先快速閱讀與確認內容。",
    usage: [
      "它是閱讀區，不是編輯器，也不是模型上下文來源。",
      "點檔案樹中的任一檔案，內容就會顯示在這裡。",
      "若要讓模型真的讀取該檔案，仍需在檔案樹勾選並按「套用釘選」。",
      "若內容很長，這個區塊本身可以捲動，不會把整頁拉長。",
    ],
  },
  "chat-panel": {
    title: "對話",
    description: "你和本地模型互動的主區域。分析結果與一般提問都會顯示在這裡。",
    usage: [
      "先開啟專案，再套用至少一個釘選檔案後開始提問。",
      "對話內容過長時，這個區塊本身會出現捲動條，不會延伸整頁。",
      "模型只會根據目前已套用的釘選檔案回答，不會自動讀取你正在預覽的檔案。",
    ],
  },
  "chat-input": {
    title: "對話輸入",
    description: "輸入你要問模型的內容。模型會根據目前已套用的釘選檔案回答。",
    usage: [
      "可直接問：『登入流程在哪些檔案？』",
      "也可下指令：『先不要改檔，先分析 bug 可能位置。』",
      "若尚未套用釘選檔案，系統會先要求你去檔案樹勾選並套用。",
    ],
  },
  "send-chat": {
    title: "送出",
    description: "把目前輸入框的問題送到模型。",
    usage: [
      "送出前請確認已開啟專案。",
      "送出後回答會顯示在對話區。",
      "若你輸入的是修改需求，系統會直接在主對話框回覆修改建議與 diff。",
      "如果目前正在開專案或下載模型，這個按鈕會被停用。",
    ],
  },
  "clear-chat": {
    title: "清空對話",
    description: "清掉目前頁面上的對話歷史，讓你重新開始一輪提問。",
    usage: [
      "只清除這次 web UI 的對話內容。",
      "也會一併清掉目前暫存的修改建議狀態。",
      "不會刪除專案、模型、摘要或檔案樹。",
    ],
  },
  "generate-edit": {
    title: "產生修改建議",
    description: "根據你目前輸入的需求，讓模型先產生一份修改建議與 diff 預覽，不會直接寫入檔案。",
    usage: [
      "必須先在檔案樹勾選相關檔案，並按「套用釘選」。",
      "建議會直接出現在主對話框中，不會另外跳出視窗。",
      "若內容有錯，可直接在同一個主對話框接著說明，例如「piece 不存在，請改用現有變數」。",
    ],
  },
  "discard-edit": {
    title: "清除建議",
    description: "把目前尚未處理的修改建議清掉，不會改動任何檔案。",
    usage: [
      "適合建議不滿意時重新生成。",
      "只會移除目前的修改建議狀態，不會刪掉主對話框裡已顯示過的歷史訊息。",
    ],
  },
  "edit-plan-status": {
    title: "修改建議狀態",
    description: "主畫面只保留一小塊狀態摘要，提醒你目前是否已有修改建議。",
    usage: [
      "尚未產生建議時，會顯示待命訊息。",
      "已有建議時，會顯示模式與摘要。",
      "如果你發現建議有錯，直接在主對話框接著描述問題即可，系統會把上一版建議當成修正對象。",
    ],
  },
};

const elements = {
  projectPath: document.getElementById("projectPath"),
  modelKey: document.getElementById("modelKey"),
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
  const hasPendingEdit = !!state.pendingEdit;

  elements.openProjectBtn.disabled = opening;
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

function requirePinnedFiles() {
  if (state.pinnedFiles.size > 0) {
    return true;
  }
  showError({
    code: "PINNED_CONTEXT_REQUIRED",
    message: "請先套用釘選檔案。",
    details: "請先在檔案樹勾選並套用至少一個檔案，模型才會根據這些檔案分析。",
  });
  setStatus("請先套用釘選檔案");
  return false;
}

function renderPendingEdit(plan) {
  state.pendingEdit = plan || null;
  updateChatPlaceholder();
}

function buildPendingEditText(plan) {
  const mode = plan?.mode || "precise";
  const sections = [
    `修改摘要：${plan?.summary || "未提供"}`,
    `模式：${mode === "advisory" ? "文字模式" : "精準模式"}`,
  ];
  if (plan?.failureReason) {
    sections.push(`精準模式未套用原因：${plan.failureReason}`);
  }
  if (plan?.needMoreContext?.length) {
    sections.push(`需要補充：${plan.needMoreContext.join("、")}`);
  }
  sections.push("");
  if (mode === "advisory") {
    if (plan?.displayText) {
      sections.push(String(plan.displayText).trim());
    } else if (Array.isArray(plan?.suggestions)) {
      sections.push(plan.suggestions.map((item) => {
        const parts = [
          `檔案：${item.path || "(未指定檔案)"}`,
          `修改位置：${item.location || "未提供"}`,
          `命中函式/區塊：${item.target || "未提供"}`,
          `原因：${item.whyHere || item.reason || "模型未提供原因"}`,
          "建議替換前片段：",
          item.before || "模型未提供原始片段。",
          "",
          "建議替換後片段：",
          item.after || "模型未提供建議片段。",
          "",
          "Diff 視窗：",
          item.diffWindow || "模型未提供 diff window。",
        ];
        if (Array.isArray(item.notes) && item.notes.length) {
          parts.push("", "補充說明：", item.notes.map((note) => `- ${note}`).join("\n"));
        }
        return parts.join("\n");
      }).join("\n\n---\n\n"));
    }
  } else if (Array.isArray(plan?.edits)) {
    sections.push(plan.edits.map((item) => {
      const parts = [
        `檔案：${item.path || "(未指定檔案)"}`,
        `修改位置：${item.location || "未提供"}`,
        `命中函式/區塊：${item.target || "未提供"}`,
        `原因：${item.reason || "未提供"}`,
        "建議替換前片段：",
        item.beforeSnippet || "未提供",
        "",
        "建議替換後片段：",
        item.afterSnippet || "未提供",
        "",
        "Diff 視窗：",
        item.diffWindow || item.diff || "未提供",
      ];
      if (Array.isArray(item.notes) && item.notes.length) {
        parts.push("", "補充說明：", item.notes.map((note) => `- ${note}`).join("\n"));
      }
      return parts.join("\n");
    }).join("\n\n"));
  }
  return sections.join("\n");
}

function updateChatPlaceholder() {
  if (state.pendingEdit) {
    elements.chatInput.placeholder = "直接描述上一版建議哪裡錯了，例如：piece 不存在，請改用現有變數。";
    return;
  }
  elements.chatInput.placeholder = "輸入你的問題或修改需求，例如：請分析登入流程涉及哪些檔案？";
}

function formatProjectSummary(summary, pinnedFiles = []) {
  const base = summary || "尚未開啟專案。";
  const pinned = Array.isArray(pinnedFiles) ? pinnedFiles.filter(Boolean) : [];
  const previewList = pinned.slice(0, 6);
  const pinnedBlock = pinned.length
    ? `\n已套用釘選檔案 (${pinned.length}):\n- ${previewList.join("\n- ")}${pinned.length > previewList.length ? `\n- +${pinned.length - previewList.length} 個` : ""}`
    : "\n已套用釘選檔案: (無)";
  return `${base}${pinnedBlock}`;
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
  state.currentPreviewPath = data.currentPreviewPath || null;
  state.pendingEdit = data.pendingEdit || null;
  state.history = data.history || [];
  elements.projectPath.value = state.projectPath;
  elements.modelKey.value = state.modelKey;
  elements.previewPath.textContent = state.currentPreviewPath || "未選擇檔案";
  elements.projectSummary.textContent = formatProjectSummary(data.summary, data.pinnedFiles || []);
  renderTree(data.tree || []);
  renderHistory(state.history);
  renderPendingEdit(state.pendingEdit);
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
  state.currentPreviewPath = null;
  elements.previewPath.textContent = "未選擇檔案";
  elements.filePreview.textContent = "點左側檔案即可預覽內容。檔案預覽僅供閱讀，不會自動加入模型上下文。";
  renderPendingEdit(null);
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
  if (!requirePinnedFiles()) {
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

async function generateEditPlan() {
  const message = elements.chatInput.value.trim();
  if (!message) {
    showError({ code: "EDIT_PLAN_FAILED", message: "請先輸入修改需求。", details: "" });
    return;
  }
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: "請先完成開啟專案。", details: "" });
    return;
  }
  if (!requirePinnedFiles()) {
    return;
  }
  clearError();
  appendMessage("user", message);
  elements.chatInput.value = "";
  setStatus("正在產生修改建議", true);
  try {
    const data = await requestJson("/api/edit/plan", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderPendingEdit(data.plan);
    const modeLabel = data.plan.mode === "advisory" ? "文字模式" : "精準模式";
    appendMessage("assistant", `已產生修改建議（${modeLabel}）\n\n${buildPendingEditText(data.plan)}`);
    setStatus("修改建議已產生");
    setUiState("ready");
  } catch (error) {
    setStatus("產生建議失敗");
    showError(normalizeError(error, "EDIT_PLAN_FAILED", "產生修改建議失敗。"));
  }
}

async function discardEditPlan() {
  if (!state.pendingEdit) return;
  try {
    await requestJson("/api/edit/discard", {
      method: "POST",
      body: JSON.stringify({}),
    });
    renderPendingEdit(null);
    setStatus("已清除修改建議");
    setUiState("ready");
  } catch (error) {
    showError(normalizeError(error, "DISCARD_EDIT_FAILED", "清除修改建議失敗。"));
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
    state.currentPreviewPath = data.path || path;
    elements.previewPath.textContent = state.currentPreviewPath;
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
    const data = await requestJson("/api/pin-files", {
      method: "POST",
      body: JSON.stringify({ files: [...state.pinnedFiles] }),
    });
    state.pinnedFiles = new Set(data.pinnedFiles || []);
    await refreshStatus();
    setStatus(`已套用 ${state.pinnedFiles.size} 個釘選檔案`);
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
  if (!requirePinnedFiles()) {
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
    if (data.plan) {
      renderPendingEdit(data.plan);
    }
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
      renderPendingEdit(null);
      setStatus(state.uiState === "ready" ? "專案已就緒" : "對話已清空");
    })
    .catch((error) => showError(normalizeError(error, "RESET_HISTORY_FAILED", "清空對話失敗。")));
}

document.querySelectorAll(".help-trigger").forEach((button) => {
  button.addEventListener("click", () => openHelp(button.dataset.help));
});

elements.projectPath.addEventListener("click", (event) => {
  if (elements.projectPath.disabled) return;
  event.preventDefault();
  pickFolder();
});
elements.projectPath.addEventListener("keydown", (event) => {
  if (elements.projectPath.disabled) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    pickFolder();
  }
});
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
