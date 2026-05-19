async function refreshStatus() {
  const data = await requestJson("/api/status");
  state.projectPath = data.projectPath || "";
  state.modelKey = data.modelKey || "gemma4";
  state.modelCapabilities = data.models || {};
  state.hardwareProfile = data.hardwareProfile || state.hardwareProfile;
  state.recommendedModelKey = data.recommendedModelKey || state.recommendedModelKey;
  state.contextOptions = data.contextOptions || state.contextOptions;
  Object.entries(state.modelCapabilities || {}).forEach(([key, model]) => {
    state.modelContextByKey[key] = Number(model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow || state.modelContextByKey[key] || 262144);
  });
  state.activeThreadId = data.activeThreadId || "";
  state.threads = data.threads || [];
  state.uiState = data.uiState || (data.projectPath ? "ready" : "idle");
  state.summaryRaw = data.summary || "";
  clearTimeout(state.pinSyncTimer);
  state.pinSyncTimer = null;
  state.pinSyncRollback = null;
  state.pendingEdit = data.pendingEdit || null;
  state.history = data.history || [];
  state.transcript = data.transcript || [];
  elements.projectPath.value = state.projectPath;
  renderModelOptions(state.modelCapabilities);
  elements.modelKey.value = state.modelKey;
  renderContextSelector();
  renderHardwareStatus();
  renderTree(data.tree || []);
  setPinnedFiles(data.pinnedFiles || []);
  renderHistory(state.history, state.transcript);
  renderThreads(state.threads);
  renderPendingEdit(state.pendingEdit);
  renderContextCoverage(null);
  if (state.uiState !== "opening" && state.currentTaskKind !== "redownload-model") {
    setUiState(state.uiState);
    if (data.projectPath) {
      setStatus(t("statuses.ready"));
    } else {
      setStatus(t("statuses.idle"));
    }
  }
  if (state.uiState === "ready") {
    loadFileTree({ query: elements.fileTreeSearch?.value || "" }).catch(() => {});
    loadCodeGraphStatus().catch(() => {});
  }
  refreshModelStatus().catch(() => {});
}

async function refreshModelStatus() {
  if (!elements.modelStatus) return;
  const data = await requestJson("/api/models");
  state.modelCapabilities = data.models || state.modelCapabilities;
  state.hardwareProfile = data.hardwareProfile || state.hardwareProfile;
  state.recommendedModelKey = data.recommendedModelKey || state.recommendedModelKey;
  renderModelOptions(state.modelCapabilities);
  const modelKey = elements.modelKey.value || state.modelKey || data.defaultModelKey || "gemma4";
  const model = data.models?.[modelKey];
  if (!model) {
    elements.modelStatus.textContent = `${t("labels.modelStatus")}: ${modelKey}`;
    renderHardwareStatus();
    return;
  }
  const installed = model.installed ? (state.language === "en" ? "installed" : "已下載") : (state.language === "en" ? "not downloaded" : "未下載");
  const ready = model.ready ? (state.language === "en" ? "ready" : "服務中") : (state.language === "en" ? "stopped" : "未啟動");
  state.modelContextByKey[modelKey] = Number(model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow || state.modelContextByKey[modelKey] || 262144);
  renderContextSelector(data.contextOptions || model.contextOptions || state.contextOptions);
  const tier = formatModelTier(model.tier);
  const recommended = model.recommended ? ` · ${state.language === "en" ? "recommended" : "推薦"}` : "";
  elements.modelStatus.textContent = `${t("labels.modelStatus")}: ${model.displayName || modelKey} · ${tier}${recommended} · ${installed} · ${ready} · port ${model.port || "-"} · ctx ${formatContextWindow(model.selectedContextWindow || model.contextWindow)}`;
  renderHardwareStatus(state.hardwareProfile, model);
}

async function updateSelectedContext() {
  const modelKey = elements.modelKey.value || state.modelKey || "gemma4";
  const contextWindow = Number(elements.contextWindowSelect?.value || state.modelContextByKey[modelKey] || 262144);
  state.modelContextByKey[modelKey] = contextWindow;
  try {
    const data = await requestJson("/api/models/context", {
      method: "POST",
      body: JSON.stringify({ modelKey, contextWindow }),
    });
    state.contextOptions = data.contextOptions || state.contextOptions;
    Object.entries(data.models || {}).forEach(([key, model]) => {
      state.modelContextByKey[key] = Number(model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow || state.modelContextByKey[key] || 262144);
    });
    renderContextSelector();
    setStatus(t("statuses.contextUpdated"));
    await refreshModelStatus();
  } catch (error) {
    showError(normalizeError(error, "MODEL_CONTEXT_FAILED", t("errors.contextUpdateFailed")));
    renderContextSelector();
  }
}

async function loadThreads() {
  try {
    const data = await requestJson("/api/threads");
    state.activeThreadId = data.activeThreadId || "";
    renderThreads(data.threads || []);
  } catch (error) {
    showError(normalizeError(error, "THREAD_FAILED", t("errors.threadFailed")));
  }
}

async function newThread() {
  try {
    const data = await requestJson("/api/threads", {
      method: "POST",
      body: JSON.stringify({}),
    });
    state.activeThreadId = data.activeThreadId || "";
    renderThreads(data.threads || []);
    state.history = [];
    state.transcript = [];
    renderHistory([], []);
    renderPendingEdit(null);
    renderContextCoverage(null);
    setStatus(t("statuses.threadCreated"));
  } catch (error) {
    showError(normalizeError(error, "THREAD_CREATE_FAILED", t("errors.threadFailed")));
  }
}

async function selectThread(threadId) {
  if (!threadId || threadId === state.activeThreadId) return;
  try {
    const data = await requestJson(`/api/threads/${encodeURIComponent(threadId)}/select`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    state.activeThreadId = data.activeThreadId || threadId;
    renderThreads(data.threads || []);
    if (data.status) {
      state.history = data.status.history || [];
      state.transcript = data.status.transcript || [];
      state.modelKey = data.status.modelKey || state.modelKey;
      elements.modelKey.value = state.modelKey;
      renderHistory(state.history, state.transcript);
      renderPendingEdit(data.status.pendingEdit || null);
    }
    setStatus(t("statuses.threadSelected"));
  } catch (error) {
    showError(normalizeError(error, "THREAD_SELECT_FAILED", t("errors.threadFailed")));
  }
}

async function renameThread(thread) {
  const nextTitle = window.prompt(state.language === "en" ? "Thread name" : "對話串名稱", thread.title || "");
  if (nextTitle === null) return;
  try {
    const data = await requestJson(`/api/threads/${encodeURIComponent(thread.id)}`, {
      method: "PATCH",
      body: JSON.stringify({ title: nextTitle }),
    });
    renderThreads(data.threads || []);
    setStatus(t("statuses.threadUpdated"));
  } catch (error) {
    showError(normalizeError(error, "THREAD_UPDATE_FAILED", t("errors.threadFailed")));
  }
}

async function deleteThread(threadId) {
  if (!window.confirm(state.language === "en" ? "Delete this thread?" : "確定刪除此對話串？")) return;
  try {
    const data = await requestJson(`/api/threads/${encodeURIComponent(threadId)}`, { method: "DELETE" });
    state.activeThreadId = data.activeThreadId || "";
    renderThreads(data.threads || []);
    if (data.status) {
      state.history = data.status.history || [];
      state.transcript = data.status.transcript || [];
      renderHistory(state.history, state.transcript);
      renderPendingEdit(data.status.pendingEdit || null);
    }
    setStatus(t("statuses.threadDeleted"));
  } catch (error) {
    showError(normalizeError(error, "THREAD_DELETE_FAILED", t("errors.threadFailed")));
  }
}
