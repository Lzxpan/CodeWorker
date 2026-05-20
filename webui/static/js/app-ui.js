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
  elements.chatInput.placeholder = t("placeholders.chatDefault");
}

function formatProjectSummary(summary, pinnedFiles = []) {
  const base = translateSummaryBase(summary || t("hints.initialSummary"));
  const pinned = Array.isArray(pinnedFiles) ? pinnedFiles.filter(Boolean) : [];
  const previewList = pinned.slice(0, 6);
  const pinnedBlock = pinned.length
    ? `\n${t("summary.pinned")} (${pinned.length}):\n- ${previewList.join("\n- ")}${pinned.length > previewList.length ? `\n- ${t("summary.moreCount", pinned.length - previewList.length)}` : ""}`
    : `\n${t("summary.pinned")}: ${t("summary.noPins")}`;
  return `${base}${pinnedBlock}`;
}

function setPinnedFiles(files = []) {
  state.pinnedFiles = new Set((files || []).filter(Boolean));
  elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
  renderTree(state.tree);
}

function formatContextWindow(value) {
  const numeric = Number(value || 0);
  if (!numeric) return "-";
  return numeric % 1024 === 0 ? `${numeric / 1024}k` : String(numeric);
}

function formatModelTier(tier, compact = false) {
  const normalized = String(tier || "standard");
  const compactZh = {
    low: "低",
    standard: "標",
    high: "高",
    extreme: "極",
  };
  const compactEn = {
    low: "L",
    standard: "S",
    high: "H",
    extreme: "X",
  };
  const zh = {
    low: "低階",
    standard: "標準",
    high: "高階",
    extreme: "極高階",
  };
  const en = {
    low: "Low",
    standard: "Standard",
    high: "High",
    extreme: "Extreme",
  };
  if (compact) {
    return (state.language === "en" ? compactEn : compactZh)[normalized] || normalized;
  }
  return (state.language === "en" ? en : zh)[normalized] || normalized;
}

function compactModelName(name, key) {
  const value = String(name || key || "");
  return value
    .replace("Qwen2.5-Coder 14B Instruct", "Qwen2.5 14B")
    .replace("Qwen3-Coder 30B A3B", "Qwen3 30B")
    .replace("DeepSeek-Coder V2 Lite", "DeepSeek V2 Lite")
    .replace("Qwen 3.5 9B Vision", "Qwen3.5 9B")
    .replace("Gemma 4 26B", "Gemma4 26B");
}

function formatModelOptionLabel(key, model) {
  const parts = [];
  if (model.recommended) {
    parts.push(state.language === "en" ? "R" : "薦");
  }
  parts.push(formatModelTier(model.tier, true));
  const size = Number(model.estimatedModelSizeGb || 0);
  const context = model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow;
  const suffix = [
    size ? `${size.toFixed(size >= 10 ? 0 : 1)}G` : "",
    context ? formatContextWindow(context) : "",
  ].filter(Boolean).join("/");
  return `${parts.map((item) => `[${item}]`).join("")} ${compactModelName(model.displayName, key)}${suffix ? ` ${suffix}` : ""}`;
}

function renderHardwareStatus(profile = state.hardwareProfile, selectedModel = null) {
  if (!elements.hardwareStatus) return;
  if (!profile) {
    elements.hardwareStatus.textContent = `${t("labels.hardwareStatus")}: ${state.language === "en" ? "not checked" : "尚未檢查"}`;
    return;
  }
  const profileName = formatModelTier(profile.profile);
  const ram = Number(profile.totalRamGb || 0);
  const gpuNames = Array.isArray(profile.gpus)
    ? profile.gpus.map((gpu) => gpu.name).filter(Boolean).slice(0, 2).join(", ")
    : "";
  const model = selectedModel || getModelCapability(elements.modelKey.value || state.modelKey);
  const backend = model.runtimeBackend || "cpu";
  const context = model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow;
  const recommendation = state.recommendedModelKey ? getModelLabel(state.recommendedModelKey) : "";
  const gpuText = gpuNames || (state.language === "en" ? "CPU only" : "僅 CPU");
  const recommendedText = recommendation
    ? `${state.language === "en" ? "Recommended" : "推薦"}: ${recommendation}`
    : "";
  elements.hardwareStatus.innerHTML = `
    <div><strong>${escapeHtml(t("labels.hardwareStatus"))}</strong>: ${escapeHtml(profileName)} · RAM ${escapeHtml(ram ? `${ram.toFixed(1)}GB` : "-")} · ${escapeHtml(gpuText)}</div>
    <div>${escapeHtml(recommendedText || (state.language === "en" ? "Recommendation unavailable" : "尚無推薦模型"))}</div>
    <div>Backend ${escapeHtml(backend)} · ctx ${escapeHtml(formatContextWindow(context))}</div>
  `;
}

function renderModelOptions(models = {}) {
  const selected = elements.modelKey.value || state.modelKey || "gemma4";
  const entries = Object.entries(models);
  if (!entries.length) return;
  entries.forEach(([key, model]) => {
    state.modelContextByKey[key] = Number(model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow || state.modelContextByKey[key] || 262144);
  });
  elements.modelKey.innerHTML = entries.map(([key, model]) => (
    `<option value="${escapeHtml(key)}">${escapeHtml(formatModelOptionLabel(key, model))}</option>`
  )).join("");
  elements.modelKey.value = models[selected] ? selected : (state.recommendedModelKey && models[state.recommendedModelKey] ? state.recommendedModelKey : (state.modelKey || entries[0][0]));
  renderContextSelector();
  renderHardwareStatus();
}

function renderContextSelector(options = state.contextOptions) {
  if (!elements.contextWindowSelect) return;
  const selectedModel = elements.modelKey.value || state.modelKey || "gemma4";
  const selectedContext = Number(state.modelContextByKey[selectedModel] || 262144);
  const modelOptions = getModelCapability(selectedModel).contextOptions;
  const normalizedOptions = Array.isArray(modelOptions) && modelOptions.length
    ? modelOptions
    : (Array.isArray(options) && options.length ? options : state.contextOptions);
  elements.contextWindowSelect.innerHTML = normalizedOptions.map((item) => (
    `<option value="${Number(item.value)}">${escapeHtml(item.label || `${Number(item.value) / 1024}k`)}</option>`
  )).join("");
  elements.contextWindowSelect.value = String(selectedContext);
}

function getRoleLabel(role, meta = {}) {
  if (role === "user") return t("roles.user");
  return meta.modelName || getModelLabel(meta.modelKey || state.modelKey) || t("roles.assistant");
}

function splitReasoningContent(content) {
  const text = String(content || "");
  const match = text.match(/<think>\n?([\s\S]*?)\n?<\/think>\n*/);
  if (!match) return { reasoning: "", answer: text };
  return {
    reasoning: match[1] || "",
    answer: text.replace(match[0], "").trim(),
  };
}

function renderReasoningHtml(reasoning, modelName) {
  if (!String(reasoning || "").trim()) return "";
  const title = state.language === "en" ? `${modelName} reasoning` : `${modelName} 思考過程`;
  return `
    <details class="reasoning-block">
      <summary>${escapeHtml(title)}</summary>
      <pre>${escapeHtml(reasoning)}</pre>
    </details>
  `;
}

function contextCoverageTranscriptHtml(coverage) {
  return `
    <section class="transcript-tool-section">
      <div class="tool-card-head">
        <strong>${escapeHtml(state.language === "en" ? "Context sent to AI" : "本次上下文")}</strong>
        <span class="badge">${escapeHtml(coverage?.truncated ? (state.language === "en" ? "excerpt" : "節錄") : (state.language === "en" ? "ready" : "已送出"))}</span>
      </div>
      <div class="tool-card-body">${escapeHtml(formatContextCoverage(coverage) || t("hints.contextCoverageHidden"))}</div>
    </section>
  `;
}

function bindTranscriptInteractions(root = elements.chatLog) {
  if (!root) return;
  root.querySelectorAll("[data-codegraph-query]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => {
      const query = button.dataset.codegraphQuery || "";
      if (!query) return;
      elements.chatInput.value = query;
      queryCodeGraph().catch((error) => showError(normalizeError(error, "CODEGRAPH_QUERY_FAILED", t("errors.codeGraphFailed"))));
    });
  });
  root.querySelectorAll(".codegraph-node, .codegraph-file, .structure-path").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => {
      const path = button.dataset.path || "";
      if (!path) return;
      elements.fileTreeSearch.value = path;
      loadFileTree({ query: path, offset: 0, limit: 500 }).catch((error) => {
        showError(normalizeError(error, "FILE_TREE_FAILED", t("errors.fileTreeFailed")));
      });
    });
  });
  root.querySelectorAll("[data-action-id] [data-action='confirm-generated']").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => confirmGeneratedFile(button.closest("[data-action-id]")?.dataset.actionId));
  });
  root.querySelectorAll("[data-action-id] [data-action='cancel-generated']").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => cancelGeneratedFile(button.closest("[data-action-id]")?.dataset.actionId));
  });
  root.querySelectorAll("[data-structure-pin]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => {
      const paths = JSON.parse(button.dataset.paths || "[]");
      pinStructureRecommendedFiles(paths);
    });
  });
  root.querySelectorAll("[data-edit-apply]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => applyEditPlan());
  });
  root.querySelectorAll("[data-edit-discard]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => discardEditPlan());
  });
  root.querySelectorAll("[data-git-diff]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => showGitDiff(button.dataset.gitDiff || ""));
  });
  root.querySelectorAll("[data-git-restore]").forEach((button) => {
    if (button.dataset.bound === "1") return;
    button.dataset.bound = "1";
    button.addEventListener("click", () => restoreEditCheckpoint(button.dataset.gitRestore || ""));
  });
}

function appendToolCard({ id = "", kind = "tool", title = "", html = "", item = null, replaceId = "" } = {}) {
  if (!elements.chatLog) return null;
  const cardId = id || item?.id || `${kind}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  if (replaceId) {
    elements.chatLog.querySelector(`[data-transcript-id="${CSS.escape(replaceId)}"]`)?.remove();
  }
  if (elements.chatLog.querySelector(`[data-transcript-id="${CSS.escape(cardId)}"]`)) {
    return elements.chatLog.querySelector(`[data-transcript-id="${CSS.escape(cardId)}"]`);
  }
  const card = document.createElement("div");
  card.className = `chat-item tool transcript-card ${kind}`;
  card.dataset.transcriptId = cardId;
  card.innerHTML = `
    <div class="chat-role">${escapeHtml(title || item?.title || (state.language === "en" ? "Tool" : "工具"))}</div>
    <div class="chat-content tool-card-content">${html}</div>
  `;
  elements.chatLog.appendChild(card);
  bindTranscriptInteractions(card);
  maintainChatAutoScroll();
  return card;
}

function renderTranscriptItem(item) {
  if (!item || typeof item !== "object") return;
  const kind = item.kind || "chat";
  const data = item.data || {};
  if (kind === "chat") {
    appendMessage(item.role || "assistant", item.content || "", data.attachments || [], { ...data, modelName: item.title || data.modelName });
    return;
  }
  if (kind === "status-context") {
    appendToolCard({ id: item.id, kind, title: item.title || (state.language === "en" ? "Context" : "上下文"), html: contextCoverageTranscriptHtml(data.contextCoverage || data), item });
    return;
  }
  if (kind === "tool-codegraph" && typeof renderCodeGraphTranscriptItem === "function") {
    appendToolCard({ id: item.id, kind, title: item.title || "CodeGraph", html: renderCodeGraphTranscriptItem(item), item });
    return;
  }
  if (kind === "tool-structure" && typeof renderStructureTranscriptItem === "function") {
    appendToolCard({ id: item.id, kind, title: item.title || t("structure.title"), html: renderStructureTranscriptItem(item), item });
    return;
  }
  if (kind === "action-generated-file" && typeof renderGeneratedActionsTranscriptItem === "function") {
    appendToolCard({ id: item.id, kind, title: item.title || (state.language === "en" ? "Generated file preview" : "生成檔案預覽"), html: renderGeneratedActionsTranscriptItem(item), item });
    return;
  }
  if ((kind === "action-edit-apply" || kind === "action-edit-restore") && typeof renderEditResultTranscriptItem === "function") {
    appendToolCard({ id: item.id, kind, title: item.title || (state.language === "en" ? "Edit action" : "檔案修改"), html: renderEditResultTranscriptItem(item), item });
    return;
  }
  appendToolCard({ id: item.id, kind, title: item.title || kind, html: `<div class="tool-card-body">${escapeHtml(item.content || "")}</div>`, item });
}

function renderTranscript(transcript = []) {
  elements.chatLog.innerHTML = "";
  startChatAutoScroll();
  const safeTranscript = Array.isArray(transcript) ? transcript : [];
  safeTranscript.forEach((item) => renderTranscriptItem(item));
  bindTranscriptInteractions(elements.chatLog);
}

function isChatNearBottom() {
  if (!elements.chatLog) return true;
  const distance = elements.chatLog.scrollHeight - elements.chatLog.scrollTop - elements.chatLog.clientHeight;
  return distance <= state.chatScroll.threshold;
}

function maintainChatAutoScroll({ force = false } = {}) {
  if (!elements.chatLog) return;
  if (!force && !state.chatScroll.followLatest) return;
  state.chatScroll.programmatic = true;
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
  window.requestAnimationFrame(() => {
    state.chatScroll.programmatic = false;
    state.chatScroll.followLatest = isChatNearBottom();
  });
}

function startChatAutoScroll() {
  state.chatScroll.followLatest = true;
  maintainChatAutoScroll({ force: true });
}

function bindChatAutoScroll() {
  if (!elements.chatLog || elements.chatLog.dataset.autoScrollBound === "1") return;
  elements.chatLog.dataset.autoScrollBound = "1";
  elements.chatLog.addEventListener("scroll", () => {
    if (state.chatScroll.programmatic) return;
    state.chatScroll.followLatest = isChatNearBottom();
  });
}

function appendMessage(role, content, attachments = [], meta = {}) {
  const normalizedContent = String(content || "").trim();
  const safeAttachments = Array.isArray(attachments) ? attachments : [];
  if (!normalizedContent && safeAttachments.length === 0) {
    return;
  }
  const item = document.createElement("div");
  item.className = `chat-item ${role}`;
  const modelName = getRoleLabel(role, meta);
  const split = role === "assistant" ? splitReasoningContent(normalizedContent) : { reasoning: "", answer: normalizedContent };
  const attachmentHtml = safeAttachments.length
    ? `<div class="chat-attachments">${safeAttachments.map((entry) => renderAttachmentHtml(entry)).join("")}</div>`
    : "";
  item.innerHTML = `
    <div class="chat-role">${escapeHtml(modelName)}</div>
    ${renderReasoningHtml(split.reasoning, modelName)}
    <div class="chat-content">${escapeHtml(split.answer)}</div>
    ${attachmentHtml}
  `;
  elements.chatLog.appendChild(item);
  maintainChatAutoScroll();
}

function appendLiveMessage(role, content = "", attachments = [], meta = {}) {
  const item = document.createElement("div");
  item.className = `chat-item ${role}`;
  const modelName = getRoleLabel(role, meta);
  const attachmentHtml = Array.isArray(attachments) && attachments.length
    ? `<div class="chat-attachments">${attachments.map((entry) => renderAttachmentHtml(entry)).join("")}</div>`
    : "";
  item.innerHTML = `
    <div class="chat-role">${escapeHtml(modelName)}</div>
    <details class="reasoning-block hidden">
      <summary>${escapeHtml(state.language === "en" ? `${modelName} reasoning` : `${modelName} 思考過程`)}</summary>
      <pre></pre>
    </details>
    <div class="chat-content">${escapeHtml(String(content || ""))}</div>
    ${attachmentHtml}
  `;
  elements.chatLog.appendChild(item);
  maintainChatAutoScroll();
  const live = {
    content: item.querySelector(".chat-content"),
    reasoning: item.querySelector(".reasoning-block"),
    reasoningBody: item.querySelector(".reasoning-block pre"),
    role: item.querySelector(".chat-role"),
  };
  live.reasoning?.addEventListener("toggle", () => scrollLiveReasoningToBottom(live));
  return live;
}

function appendLiveText(target, text) {
  if (!target || !text) return;
  target.textContent += text;
  maintainChatAutoScroll();
}

function scrollLiveReasoningToBottom(live) {
  if (!live?.reasoningBody) return;
  if (live.reasoning?.open) {
    live.reasoningBody.scrollTop = live.reasoningBody.scrollHeight;
  }
  maintainChatAutoScroll();
}

function appendLiveReasoning(live, text) {
  if (!live?.reasoningBody || !text) return;
  live.reasoning?.classList.remove("hidden");
  live.reasoningBody.textContent += text;
  scrollLiveReasoningToBottom(live);
}

async function streamChat(payload, onEvent) {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    let details = "";
    try {
      const parsed = await response.json();
      details = parsed?.error?.details || parsed?.error?.message || response.statusText;
    } catch {
      details = response.statusText;
    }
    throw { code: "CHAT_FAILED", message: t("errors.chatFailed"), details };
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamFinished = false;
  const processFrame = (frame) => {
    const lines = frame.split("\n");
    const eventLine = lines.find((line) => line.startsWith("event:"));
    const dataLines = lines.filter((line) => line.startsWith("data:"));
    if (!dataLines.length) return;
    const event = eventLine ? eventLine.slice(6).trim() : "message";
    let parsed = {};
    try {
      parsed = JSON.parse(dataLines.map((line) => line.slice(5).trim()).join("\n") || "{}");
    } catch {
      parsed = {};
    }
    onEvent(event, parsed);
    if (event === "done" || event === "error") {
      streamFinished = true;
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      processFrame(frame);
      if (streamFinished) break;
    }
    if (streamFinished) {
      try {
        await reader.cancel();
      } catch {
        // The server may have already closed the SSE stream.
      }
      break;
    }
  }
  if (!streamFinished && buffer.trim()) {
    processFrame(buffer);
  }
}

function renderHistory(history, transcript = state.transcript) {
  if (Array.isArray(transcript) && transcript.length) {
    renderTranscript(transcript);
    return;
  }
  elements.chatLog.innerHTML = "";
  startChatAutoScroll();
  (Array.isArray(history) ? history : []).forEach((item) => appendMessage(item.role, item.content, item.attachments || [], item));
}

function renderThreads(threads = []) {
  state.threads = Array.isArray(threads) ? threads : [];
  if (!elements.threadList) return;
  elements.threadList.innerHTML = "";
  if (!state.threads.length) {
    elements.threadList.classList.add("empty");
    elements.threadList.textContent = state.language === "en" ? "No threads yet." : "尚無對話串。";
    return;
  }
  elements.threadList.classList.remove("empty");
  state.threads.forEach((thread) => {
    const item = document.createElement("div");
    item.className = `thread-item${thread.active ? " is-active" : ""}`;
    const title = escapeHtml(thread.title || (state.language === "en" ? "New chat" : "新對話"));
    const meta = `${thread.modelName || thread.modelKey || ""} · ${thread.updatedAtText || ""}`;
    item.innerHTML = `
      <button type="button" class="thread-title">${title}</button>
      <div class="thread-meta">${escapeHtml(meta)}</div>
      <div class="thread-summary">${escapeHtml(thread.summary || "")}</div>
      <div class="thread-actions">
        <button type="button" data-action="rename">${escapeHtml(t("buttons.renameThread"))}</button>
        <button type="button" data-action="delete">${escapeHtml(t("buttons.deleteThread"))}</button>
      </div>
    `;
    item.querySelector(".thread-title")?.addEventListener("click", () => selectThread(thread.id));
    item.querySelector('[data-action="rename"]')?.addEventListener("click", () => renameThread(thread));
    item.querySelector('[data-action="delete"]')?.addEventListener("click", () => deleteThread(thread.id));
    elements.threadList.appendChild(item);
  });
}

function applyTranslations() {
  document.documentElement.lang = t("htmlLang");
  const appName = state.appName || t("brandTitle");
  document.title = state.appName ? `${appName} Web UI` : t("pageTitle");
  elements.brandTitle.textContent = appName;
  elements.brandSubtitle.textContent = t("brandSubtitle");
  elements.langZhBtn.textContent = t("languageSwitch.zh");
  elements.langEnBtn.textContent = t("languageSwitch.en");
  elements.langZhBtn.classList.toggle("is-active", state.language === "zh-Hant");
  elements.langEnBtn.classList.toggle("is-active", state.language === "en");
  elements.projectPathLabel.textContent = t("labels.projectPath");
  elements.projectPath.placeholder = t("placeholders.projectPath");
  elements.modelKeyLabel.textContent = t("labels.model");
  elements.openProjectBtn.textContent = t("buttons.openProject");
  elements.analyzeBtn.textContent = t("buttons.analyzeProject");
  if (elements.sidebarStatusSummary) elements.sidebarStatusSummary.textContent = t("labels.statusDetails");
  elements.firstRunHint.textContent = t("hints.firstRun");
  elements.errorPanelTitle.textContent = t("headings.errorPanel");
  elements.errorActionBtn.textContent = t("buttons.redownloadModel");
  elements.dismissErrorBtn.textContent = t("buttons.dismiss");
  elements.projectSummaryTitle.textContent = t("headings.projectSummary");
  elements.refreshStatusBtn.textContent = t("buttons.refresh");
  elements.fileTreeTitle.textContent = t("headings.fileTree");
  elements.chatPanelTitle.textContent = t("headings.chatPanel");
  if (elements.threadPanelTitle) elements.threadPanelTitle.textContent = t("headings.threadPanel");
  if (elements.codeGraphHint) elements.codeGraphHint.textContent = t("hints.codeGraphHint");
  if (elements.codeGraphUsePromptBtn) elements.codeGraphUsePromptBtn.textContent = t("buttons.codeGraphUsePrompt");
  if (elements.codeGraphRebuildBtn) elements.codeGraphRebuildBtn.textContent = t("buttons.codeGraphRebuild");
  if (elements.codeGraphPinBtn) elements.codeGraphPinBtn.textContent = t("buttons.codeGraphPin");
  if (elements.editPlanBtn) elements.editPlanBtn.textContent = t("buttons.editPlan");
  if (elements.gitDiffBtn) elements.gitDiffBtn.textContent = t("buttons.gitDiff");
  if (elements.gitCheckpointBtn) elements.gitCheckpointBtn.textContent = t("buttons.gitCheckpoint");
  renderContextCoverage(state.lastContextCoverage);
  elements.chatInputLabel.textContent = t("labels.chatInput");
  elements.chatImageLabel.textContent = t("labels.chatImage");
  elements.attachImageBtn.textContent = t("buttons.attachImage");
  elements.chatImagePasteHint.textContent = t("hints.imagePasteHint");
  elements.removeChatImageBtn.textContent = t("buttons.removeImage");
  if (elements.contextWindowLabel) elements.contextWindowLabel.textContent = t("labels.contextWindow");
  if (elements.newThreadBtn) elements.newThreadBtn.textContent = t("buttons.newThread");
  elements.sendChatBtn.textContent = t("buttons.send");
  elements.clearChatBtn.textContent = t("buttons.clearChat");
  elements.helpTitle.textContent = state.openHelpKey ? (localizeHelpEntry(state.openHelpKey)?.title || t("headings.helpModal")) : t("headings.helpModal");
  elements.closeHelpBtn.textContent = t("buttons.dismiss");
  updateChatPlaceholder();
  elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
  renderTree(state.tree);
  renderHistory(state.history, state.transcript);
  renderThreads(state.threads);
  renderContextSelector();
  renderHardwareStatus();
  if (typeof renderCodeGraphResults === "function" && state.codeGraphLastResult) {
    renderCodeGraphResults(state.codeGraphLastResult, state.codeGraphLastRebuild ? { rebuild: state.codeGraphLastRebuild } : {});
  } else if (typeof renderCodeGraphStatusPanel === "function" && state.codeGraphStatus) {
    renderCodeGraphStatusPanel(state.codeGraphStatus);
  }
  renderChatImagePreview();
  setAiBusy(state.aiBusy, t("labels.aiBusy"));
  setStatus(state.lastStatusText, state.lastStatusBusy);
  renderProgress(state.lastProgress.progress, state.lastProgress.step, state.lastProgress.title);
  if (state.lastError) {
    showError(state.lastError);
  }
  if (state.openHelpKey) {
    const entry = localizeHelpEntry(state.openHelpKey);
    if (entry) {
      elements.helpTitle.textContent = entry.title;
      elements.helpBody.innerHTML = renderHelpContent(entry);
    }
  }
}

function setLanguage(language) {
  state.language = language === "en" ? "en" : "zh-Hant";
  localStorage.setItem("codeworker.language", state.language);
  applyTranslations();
}
