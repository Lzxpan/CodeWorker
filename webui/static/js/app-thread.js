async function refreshStatus() {
  const data = await requestJson("/api/status");
  state.appVersion = data.appVersion || state.appVersion;
  state.appName = data.appName || state.appName;
  applyTranslations();
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
  state.fileMetaByPath = data.fileMeta || state.fileMetaByPath || {};
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

async function calibrateSelectedModelContext() {
  const modelKey = elements.modelKey.value || state.modelKey || "gemma4";
  const contextWindow = Number(elements.contextWindowSelect?.value || state.modelContextByKey[modelKey] || 32768);
  const button = elements.contextCalibrateBtn;
  if (button) button.disabled = true;
  setStatus(state.language === "en" ? "Measuring context capacity" : "正在測試 context 可送出 KB", true);
  setAiBusy(true, state.language === "en" ? "Measuring model context capacity" : "正在實測模型 context 容量");
  try {
    const data = await requestJson("/api/models/context-calibration", {
      method: "POST",
      body: JSON.stringify({ modelKey, contexts: [contextWindow] }),
    });
    state.modelCapabilities = data.models || state.modelCapabilities;
    const structured = Number(data.structuredEditChars || data.calibration?.structuredEditChars || 0);
    const maxInput = Number(data.maxInputChars || data.calibration?.maxInputChars || 0);
    const measuredAt = String(data.measuredAt || data.calibration?.measuredAt || "");
    appendToolCard({
      kind: "status-context",
      title: state.language === "en" ? "Context capacity measured" : "Context 容量實測",
      html: `
        <section class="transcript-tool-section">
          <div class="tool-card-head">
            <strong>${escapeHtml(state.language === "en" ? "Context capacity measured" : "Context 容量實測")}</strong>
            <span class="badge">${escapeHtml(modelKey)}</span>
          </div>
          <div class="tool-card-body">
            <div>${escapeHtml(state.language === "en" ? "Structured edit budget" : "修改計畫可送出上限")}：${escapeHtml(structured ? `${Math.round(structured / 1024)}KB (${structured} chars)` : "-")}</div>
            <div>${escapeHtml(state.language === "en" ? "Max input budget" : "一般輸入上限")}：${escapeHtml(maxInput ? `${Math.round(maxInput / 1024)}KB (${maxInput} chars)` : "-")}</div>
            <div>${escapeHtml(state.language === "en" ? "Context tested" : "測試 context")}：${escapeHtml(formatContextWindow(contextWindow))}</div>
            ${measuredAt ? `<div>${escapeHtml(state.language === "en" ? "Measured at" : "測試時間")}：${escapeHtml(measuredAt)}</div>` : ""}
          </div>
        </section>
      `,
    });
    renderModelOptions(state.modelCapabilities);
    setStatus(state.language === "en" ? "Context capacity measured" : "Context 容量實測完成");
  } catch (error) {
    showError(normalizeError(error, "MODEL_CONTEXT_CALIBRATION_FAILED", state.language === "en" ? "Context capacity measurement failed." : "Context 容量實測失敗。"));
    setStatus(state.language === "en" ? "Context measurement failed" : "Context 實測失敗");
  } finally {
    if (button) button.disabled = false;
    setAiBusy(false);
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
