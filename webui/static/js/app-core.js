const elements = {
  brandTitle: document.getElementById("brandTitle"),
  brandSubtitle: document.getElementById("brandSubtitle"),
  langZhBtn: document.getElementById("langZhBtn"),
  langEnBtn: document.getElementById("langEnBtn"),
  projectPathLabel: document.getElementById("projectPathLabel"),
  projectPath: document.getElementById("projectPath"),
  modelKeyLabel: document.getElementById("modelKeyLabel"),
  modelKey: document.getElementById("modelKey"),
  openProjectBtn: document.getElementById("openProjectBtn"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  firstRunHint: document.getElementById("firstRunHint"),
  sidebarStatusDetails: document.getElementById("sidebarStatusDetails"),
  sidebarStatusSummary: document.querySelector("#sidebarStatusDetails summary"),
  modelStatus: document.getElementById("modelStatus"),
  hardwareStatus: document.getElementById("hardwareStatus"),
  errorPanelTitle: document.getElementById("errorPanelTitle"),
  refreshStatusBtn: document.getElementById("refreshStatusBtn"),
  projectSummaryTitle: document.getElementById("projectSummaryTitle"),
  projectSummary: document.getElementById("projectSummary"),
  fileTreeTitle: document.getElementById("fileTreeTitle"),
  fileTreeCount: document.getElementById("fileTreeCount"),
  fileTreeSearch: document.getElementById("fileTreeSearch"),
  fileTree: document.getElementById("fileTree"),
  chatPanelTitle: document.getElementById("chatPanelTitle"),
  chatLog: document.getElementById("chatLog"),
  contextCoverageBanner: document.getElementById("contextCoverageBanner"),
  agentPanel: document.getElementById("agentPanel"),
  pendingActionPanel: document.getElementById("pendingActionPanel"),
  structurePanel: document.getElementById("structurePanel"),
  codeGraphToolbar: document.getElementById("codeGraphToolbar"),
  codeGraphHint: document.getElementById("codeGraphHint"),
  codeGraphUsePromptBtn: document.getElementById("codeGraphUsePromptBtn"),
  codeGraphRebuildBtn: document.getElementById("codeGraphRebuildBtn"),
  codeGraphPinBtn: document.getElementById("codeGraphPinBtn"),
  codeGraphResults: document.getElementById("codeGraphResults"),
  chatForm: document.getElementById("chatForm"),
  chatInputLabel: document.getElementById("chatInputLabel"),
  chatInput: document.getElementById("chatInput"),
  chatImageLabel: document.getElementById("chatImageLabel"),
  attachImageBtn: document.getElementById("attachImageBtn"),
  chatImageInput: document.getElementById("chatImageInput"),
  chatImagePasteHint: document.getElementById("chatImagePasteHint"),
  chatImagePreview: document.getElementById("chatImagePreview"),
  removeChatImageBtn: document.getElementById("removeChatImageBtn"),
  contextWindowLabel: document.getElementById("contextWindowLabel"),
  contextWindowSelect: document.getElementById("contextWindowSelect"),
  sendChatBtn: document.getElementById("sendChatBtn"),
  clearChatBtn: document.getElementById("clearChatBtn"),
  threadPanelTitle: document.getElementById("threadPanelTitle"),
  threadList: document.getElementById("threadList"),
  newThreadBtn: document.getElementById("newThreadBtn"),
  aiActivity: document.getElementById("aiActivity"),
  aiActivityText: document.getElementById("aiActivityText"),
  chatBusyBar: document.getElementById("chatBusyBar"),
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

function getLocale() {
  return I18N[state.language] || I18N["zh-Hant"];
}

function getNested(source, path) {
  return path.split(".").reduce((current, key) => (current && key in current ? current[key] : undefined), source);
}

function t(path, ...args) {
  const value = getNested(getLocale(), path);
  if (typeof value === "function") {
    return value(...args);
  }
  return value ?? path;
}

function localizeHelpEntry(helpKey) {
  return HELP_CONTENT[helpKey]?.[state.language] || HELP_CONTENT[helpKey]?.["zh-Hant"] || null;
}

function translateRuntimeText(text) {
  const input = String(text || "");
  if (!input || state.language === "zh-Hant") return input;
  const replacements = [
    [/待命/g, "Idle"],
    [/等待中/g, "Waiting"],
    [/專案已就緒/g, "Project ready"],
    [/建立背景任務/g, "Creating background task"],
    [/開啟資料夾選取視窗/g, "Opening folder picker"],
    [/選擇資料夾失敗/g, "Folder selection failed"],
    [/正在開啟專案/g, "Opening project"],
    [/開啟失敗/g, "Open failed"],
    [/正在重新下載模型/g, "Redownloading model"],
    [/模型已重新下載/g, "Model redownloaded"],
    [/模型重新下載失敗/g, "Model redownload failed"],
    [/正在分析/g, "Analyzing"],
    [/分析完成/g, "Analysis complete"],
    [/分析失敗/g, "Analysis failed"],
    [/更新上下文/g, "Updating context"],
    [/更新失敗/g, "Context update failed"],
    [/正在思考/g, "Thinking"],
    [/對話失敗/g, "Chat failed"],
    [/讀取中\.\.\./g, "Loading..."],
    [/驗證專案路徑/g, "Validating project path"],
    [/正在檢查專案路徑/g, "Checking project path"],
    [/準備 Git 工作區/g, "Preparing Git workspace"],
    [/正在初始化或檢查 git repository/g, "Initializing or checking git repository"],
    [/Git 工作區完成/g, "Git workspace ready"],
    [/已完成 git 初始化與基線快照/g, "Git initialization and baseline snapshot completed"],
    [/啟動本地模型/g, "Starting local model"],
    [/正在驗證模型並啟動 llama-server/g, "Validating model and starting llama-server"],
    [/索引專案/g, "Indexing project"],
    [/正在掃描檔案、入口與測試位置/g, "Scanning files, entry points, and test locations"],
    [/完成/g, "Done"],
    [/專案已開啟/g, "Project opened"],
    [/失敗/g, "Failed"],
    [/重新下載模型/g, "Redownload model"],
    [/驗證模型/g, "Validating model"],
    [/正在確認模型設定/g, "Checking model configuration"],
    [/模型重新下載完成/g, "Model redownload completed"],
    [/已下載/g, "Downloaded"],
    [/即將下載/g, "Preparing to download"],
    [/解析模型來源/g, "Resolving model source"],
    [/準備下載/g, "Preparing download"],
    [/開啟專案失敗/g, "Open project failed"],
  ];
  return replacements.reduce((result, [pattern, replacement]) => result.replace(pattern, replacement), input);
}

function localizeError(error) {
  if (!error) return error;
  if (state.language === "zh-Hant") return error;
  const codeMap = {
    PINNED_CONTEXT_REQUIRED: {
      message: t("errors.pinnedRequiredMessage"),
      details: t("errors.pinnedRequiredDetails"),
    },
    PROJECT_NOT_READY: {
      message: t("errors.projectNotReady"),
      details: "",
    },
    PROJECT_PATH_INVALID: {
      message: t("errors.projectPathInvalid"),
      details: "",
    },
    PICK_FOLDER_FAILED: {
      message: t("errors.pickFolderFailed"),
    },
    OPEN_PROJECT_FAILED: {
      message: t("errors.openProjectFailed"),
    },
    MODEL_DOWNLOAD_FAILED: {
      message: t("errors.modelDownloadFailed"),
    },
    ANALYZE_FAILED: {
      message: t("errors.analyzeFailed"),
    },
    FILE_TREE_FAILED: {
      message: t("errors.fileTreeFailed"),
    },
    PIN_FILES_FAILED: {
      message: t("errors.pinFilesFailed"),
    },
    CHAT_FAILED: {
      message: t("errors.chatFailed"),
    },
    IMAGE_UPLOAD_FAILED: {
      message: t("errors.imageUploadFailed"),
    },
    FILE_UPLOAD_FAILED: {
      message: t("errors.imageUploadFailed"),
    },
    MODEL_CONTEXT_FAILED: {
      message: t("errors.contextUpdateFailed"),
    },
    MODEL_CONTEXT_INVALID: {
      message: t("errors.contextUpdateFailed"),
    },
    THREAD_CREATE_FAILED: { message: t("errors.threadFailed") },
    THREAD_SELECT_FAILED: { message: t("errors.threadFailed") },
    THREAD_UPDATE_FAILED: { message: t("errors.threadFailed") },
    THREAD_DELETE_FAILED: { message: t("errors.threadFailed") },
    FILE_GENERATION_FAILED: { message: t("errors.fileGenerationFailed") },
    FILE_GENERATION_INVALID: { message: t("errors.fileGenerationFailed") },
    FILE_GENERATION_CONFIRM_FAILED: { message: t("errors.fileGenerationFailed") },
    FILE_GENERATION_CANCEL_FAILED: { message: t("errors.fileGenerationFailed") },
    MODEL_EMPTY_REPLY: {
      message: t("errors.modelEmptyReply"),
    },
    RESET_HISTORY_FAILED: {
      message: t("errors.resetHistoryFailed"),
    },
    MODEL_READY: {
      message: t("errors.modelReady"),
      details: t("errors.modelReadyDetails"),
    },
  };
  const localized = codeMap[error.code] || {};
  return {
    ...error,
    message: localized.message || translateRuntimeText(error.message),
    details: localized.details || translateRuntimeText(error.details),
  };
}

function translateSummaryBase(summary) {
  const input = String(summary || "");
  if (!input || state.language === "zh-Hant") return input;
  return input
    .replace(/^專案路徑:/gm, "Project path:")
    .replace(/^檔案數量\(已掃描\):/gm, "Scanned files:")
    .replace(/^估計文字檔總大小:/gm, "Estimated text size:")
    .replace(/^主要語言:/gm, "Primary languages:")
    .replace(/^可能入口檔案:/gm, "Possible entry points:")
    .replace(/^測試相關檔案:/gm, "Test-related files:")
    .replace(/未明確找到/g, t("summary.notFound"))
    .replace(/\b無\b/g, t("summary.none"));
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function renderAttachmentHtml(attachment) {
  if (!attachment) return "";
  const label = escapeHtml(attachment.name || t("labels.chatImage"));
  const dimensions = Number(attachment.width || 0) > 0 && Number(attachment.height || 0) > 0
    ? `${attachment.width}x${attachment.height}`
    : "";
  const duration = Number(attachment.durationSeconds || 0) > 0 ? `${Number(attachment.durationSeconds).toFixed(1)}s` : "";
  const keyframes = Number(attachment.keyframeCount || 0) > 0 ? `${attachment.keyframeCount} keyframes` : "";
  const videoMode = attachment.videoAnalysisMode ? `mode:${attachment.videoAnalysisMode}` : "";
  const transcript = attachment.transcriptStatus ? `stt:${attachment.transcriptStatus}` : "";
  const transcriptChars = Number(attachment.transcriptChars || 0) > 0 ? `${attachment.transcriptChars} transcript chars` : "";
  const sha = String(attachment.sha256 || attachment.originalSha256 || "").trim();
  const meta = [
    attachment.kind,
    attachment.mimeType,
    dimensions,
    duration,
    keyframes,
    videoMode,
    transcript,
    transcriptChars,
    attachment.sizeBytes ? formatBytes(attachment.sizeBytes) : "",
    attachment.extractionStatus,
    sha ? `sha:${sha.slice(0, 8)}` : "",
  ].filter(Boolean).join(" | ");
  const preview = attachment.previewUrl
    ? `<img class="chat-attachment-preview" src="${attachment.previewUrl}" alt="${label}">`
    : "";
  return `
    <div class="chat-attachment-card">
      ${preview}
      <div class="chat-attachment-meta">
        <strong>${label}</strong>
        <span>${escapeHtml(meta)}</span>
      </div>
    </div>
  `;
}

function renderChatImagePreview() {
  const attachments = state.chatAttachments || [];
  elements.chatImagePreview.innerHTML = "";
  elements.chatImagePreview.classList.toggle("hidden", attachments.length === 0);
  elements.removeChatImageBtn.classList.toggle("hidden", attachments.length === 0);
  if (!attachments.length) return;
  elements.chatImagePreview.innerHTML = attachments.map((entry) => renderAttachmentHtml(entry)).join("");
}

function formatContextCoverage(coverage) {
  if (!coverage || typeof coverage !== "object") {
    return "";
  }
  const mode = String(coverage.mode || "");
  const memorySuffix = (() => {
    const historyItems = Number(coverage.memoryHistoryItems || 0);
    const summaryChars = Number(coverage.memorySummaryChars || 0);
    if (!historyItems && !summaryChars) return "";
    if (state.language === "en") {
      return ` Memory: ${summaryChars > 0 ? `${summaryChars} compressed char(s), ` : ""}${historyItems} recent item(s).`;
    }
    return ` 記憶：${summaryChars > 0 ? `壓縮摘要 ${summaryChars} 字，` : ""}最近 ${historyItems} 筆。`;
  })();
  if (mode === "history-continuation") {
    const historyItems = Number(coverage.historyItems || 0);
    if (state.language === "en") {
      return `Conversation continuation: reused recent chat history (${historyItems} item(s)); full-project RAG was not added.`;
    }
    return `對話續寫：沿用最近對話歷史（${historyItems} 筆），本輪未額外加入全專案 RAG。`;
  }
  if (mode === "project-cache" || mode === "project-rag") {
    const filesSent = Number(coverage.filesSent || 0);
    const selectedFiles = Number(coverage.selectedFiles || filesSent);
    const indexFiles = Number(coverage.indexFiles || selectedFiles);
    const graph = coverage.codeGraph && typeof coverage.codeGraph === "object" ? coverage.codeGraph : null;
    const graphNodes = graph ? Number(graph.nodesSent || 0) : 0;
    const graphEdges = graph ? Number(graph.edgesSent || 0) : 0;
    const graphText = graphNodes || graphEdges
      ? (state.language === "en"
        ? ` Code graph: ${graphNodes} symbol(s), ${graphEdges} relationship(s).`
        : ` Code graph：${graphNodes} 個 symbol、${graphEdges} 個關聯。`)
      : "";
    const rebuilt = Boolean(coverage.indexRebuilt);
    if (state.language === "en") {
      return `Full-project search context: ${rebuilt ? "rebuilt" : "reused"} local index, ${indexFiles} indexed file(s), sent ${filesSent}/${selectedFiles} matching summary/chunk item(s).${graphText}${memorySuffix}`;
    }
    return `全專案搜尋上下文：${rebuilt ? "已重建" : "沿用"}本機索引，已索引 ${indexFiles} 個檔案，本次送出 ${filesSent}/${selectedFiles} 個命中摘要/片段。${graphText}${memorySuffix}`;
  }
  if (mode === "memory") {
    return state.language === "en" ? `No project context used.${memorySuffix}` : `未使用專案上下文。${memorySuffix}`;
  }
  const filesSent = Number(coverage.filesSent || 0);
  const selectedFiles = Number(coverage.selectedFiles || filesSent);
  const fullCount = Number(coverage.fullCount || 0);
  const excerptCount = Number(coverage.excerptCount || 0);
  const omittedFiles = Number(coverage.omittedFiles || 0);
  if (state.language === "en") {
    const parts = [
      `Context: sent ${filesSent}/${selectedFiles} pinned file(s)`,
      excerptCount > 0 ? `(${fullCount} full, ${excerptCount} excerpt)` : "(all full)",
    ];
    if (omittedFiles > 0) {
      parts.push(`, omitted ${omittedFiles}`);
    }
    if (coverage.truncated) {
      parts.push(". The model did not receive every file in full.");
    }
    return `${parts.join("")}${memorySuffix}`;
  }
  const parts = [
    `本次上下文：已送出 ${filesSent}/${selectedFiles} 個釘選檔案`,
    excerptCount > 0 ? `（完整 ${fullCount}、節錄 ${excerptCount}）` : "（全部為完整內容）",
  ];
  if (omittedFiles > 0) {
    parts.push(`，另有 ${omittedFiles} 個未送出`);
  }
  if (coverage.truncated) {
    parts.push("。模型沒有讀到所有檔案的完整內容。");
  }
  return `${parts.join("")}${memorySuffix}`;
}

function renderContextCoverage(coverage, options = {}) {
  state.lastContextCoverage = coverage || null;
  const text = formatContextCoverage(state.lastContextCoverage);
  if (options.appendToTranscript && state.lastContextCoverage) {
    appendToolCard({
      kind: "status-context",
      title: state.language === "en" ? "Context" : "本次上下文",
      html: contextCoverageTranscriptHtml(state.lastContextCoverage),
    });
  }
  if (!text) {
    elements.contextCoverageBanner.classList.add("hidden");
    return;
  }
  elements.contextCoverageBanner.textContent = text;
  elements.contextCoverageBanner.dataset.mode = state.lastContextCoverage?.truncated ? "excerpt" : "full";
  elements.contextCoverageBanner.classList.add("hidden");
}

async function requestJson(url, options = {}) {
  const defaultHeaders = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
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
  state.lastStatusText = text;
  state.lastStatusBusy = busy;
  elements.statusBadge.textContent = translateRuntimeText(text);
  elements.statusBadge.dataset.busy = busy ? "1" : "0";
}

function setAiBusy(isBusy, text = "") {
  state.aiBusy = !!isBusy;
  const message = text || t("labels.aiBusy");
  if (elements.aiActivity) {
    elements.aiActivity.classList.toggle("hidden", !state.aiBusy);
    elements.aiActivity.setAttribute("aria-label", message);
  }
  if (elements.aiActivityText) {
    elements.aiActivityText.textContent = message;
  }
  if (elements.chatBusyBar) {
    elements.chatBusyBar.classList.toggle("hidden", !state.aiBusy);
  }
  if (elements.chatLog) {
    elements.chatLog.setAttribute("aria-busy", state.aiBusy ? "true" : "false");
  }
  setUiState(state.uiState);
}

function setUiState(nextState) {
  state.uiState = nextState;
  const ready = nextState === "ready";
  const opening = nextState === "opening";
  const busy = opening || state.currentTaskKind === "redownload-model" || state.aiBusy;
  const canChat = !busy;
  const hasPendingEdit = !!state.pendingEdit;

  elements.openProjectBtn.disabled = opening;
  elements.modelKey.disabled = opening;
  elements.projectPath.disabled = opening;
  elements.analyzeBtn.disabled = !ready || busy;
  elements.sendChatBtn.disabled = !canChat;
  elements.chatInput.disabled = !canChat;
  elements.clearChatBtn.disabled = busy;
  elements.attachImageBtn.disabled = !canChat;
  elements.removeChatImageBtn.disabled = !canChat;
  if (elements.contextWindowSelect) elements.contextWindowSelect.disabled = opening;
  if (elements.newThreadBtn) elements.newThreadBtn.disabled = busy;
}

function renderProgress(progress = 0, step = "", title = t("progress.defaultTitle")) {
  state.lastProgress = { progress, step, title };
  if (state.uiState === "opening" || state.currentTaskKind === "redownload-model") {
    elements.progressPanel.classList.remove("hidden");
  } else {
    elements.progressPanel.classList.add("hidden");
  }
  elements.progressTitle.textContent = translateRuntimeText(title);
  elements.progressPercent.textContent = `${progress}%`;
  elements.progressBar.style.width = `${progress}%`;
  elements.progressStep.textContent = translateRuntimeText(step || t("progress.waiting"));
}

function renderHelpContent(entry) {
  const sections = [`<p>${escapeHtml(entry.description || "")}</p>`];
  if (entry.usage?.length) {
    sections.push(`<h3>${escapeHtml(t("helpSections.usage"))}</h3>`);
    sections.push(`<ul>${entry.usage.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  if (entry.notes?.length) {
    sections.push(`<h3>${escapeHtml(t("helpSections.notes"))}</h3>`);
    sections.push(`<ul>${entry.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`);
  }
  return sections.join("");
}

function openHelp(helpKey) {
  state.openHelpKey = helpKey;
  const entry = localizeHelpEntry(helpKey);
  if (!entry) return;
  elements.helpTitle.textContent = entry.title;
  elements.helpBody.innerHTML = renderHelpContent(entry);
  elements.helpModal.classList.remove("hidden");
  elements.helpModal.setAttribute("aria-hidden", "false");
}

function closeHelp() {
  state.openHelpKey = null;
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
  const localized = localizeError(error);
  elements.errorPanel.classList.remove("hidden");
  elements.errorCode.textContent = localized.code || "";
  elements.errorMessage.textContent = localized.message || t("errors.unexpected");
  elements.errorDetails.textContent = localized.details || "";
  const meta = [];
  if (localized.logPath) meta.push(`Log: ${localized.logPath}`);
  if (localized.modelKey) meta.push(`Model: ${localized.modelKey}`);
  elements.errorMeta.textContent = meta.join(" | ");
  if (localized.action === "redownload-model") {
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

function requirePinnedFiles({ allowWithoutPins = false } = {}) {
  if (allowWithoutPins || state.pinnedFiles.size > 0) {
    return true;
  }
  showError({
    code: "PINNED_CONTEXT_REQUIRED",
    message: t("errors.pinnedRequiredMessage"),
    details: t("errors.pinnedRequiredDetails"),
  });
  setStatus(t("errors.pinnedRequiredMessage"));
  return false;
}

function clearChatImage({ silent = false } = {}) {
  state.chatAttachments = [];
  elements.chatImageInput.value = "";
  renderChatImagePreview();
  if (!silent) {
    setStatus(t("statuses.imageRemoved"));
  }
}

function getModelCapability(modelKey) {
  return state.modelCapabilities?.[modelKey] || {};
}

function selectedModelSupportsImages() {
  return !!getModelCapability(elements.modelKey.value || state.modelKey).supportsImages;
}

function getModelLabel(modelKey) {
  const capability = getModelCapability(modelKey);
  return capability.displayName || modelKey || "model";
}

async function uploadImageData({ name, mimeType, data }) {
  clearError();
  setStatus(t("statuses.uploadingImage"), true);
  return requestJson("/api/uploads/file", {
    method: "POST",
    body: JSON.stringify({ name, mimeType, data }),
  });
}

async function attachImageFile(file) {
  if (!file) return;
  const mimeType = String(file.type || "application/octet-stream").toLowerCase();
  const data = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed to read image."));
    reader.readAsDataURL(file);
  });
  try {
    const attachment = await uploadImageData({
      name: file.name || "attachment",
      mimeType,
      data,
    });
    state.chatAttachments.push({
      ...attachment,
      previewUrl: attachment.kind === "image" && typeof data === "string" ? data : "",
    });
    renderChatImagePreview();
    setStatus(t("statuses.imageAttached"));
  } catch (error) {
    setStatus(t("statuses.chatFailed"));
    showError(normalizeError(error, "IMAGE_UPLOAD_FAILED", t("errors.imageUploadFailed")));
  }
}
