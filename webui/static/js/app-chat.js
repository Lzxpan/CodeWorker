function renderGeneratedFileAction(action) {
  renderGeneratedFileActions(action ? [action] : []);
}

function renderGeneratedFileActions(actions) {
  const safeActions = Array.isArray(actions) ? actions.filter(Boolean) : [];
  if (!safeActions.length) {
    elements.pendingActionPanel.classList.add("hidden");
    elements.pendingActionPanel.innerHTML = "";
    return;
  }
  elements.pendingActionPanel.classList.add("hidden");
  const title = safeActions.length > 1
    ? (state.language === "en" ? "Generated file previews" : "生成檔案預覽")
    : (state.language === "en" ? "Generated file preview" : "生成檔案預覽");
  appendToolCard({
    kind: "action-generated-file",
    title,
    html: renderGeneratedActionsHtml(safeActions),
  });
  bindTranscriptInteractions(elements.chatLog);
}

function renderGeneratedFileActionCard(action) {
  if (!action) return "";
  const overwriteText = action.overwrites
    ? (state.language === "en" ? "This will overwrite an existing file." : "這會覆蓋既有檔案。")
    : (state.language === "en" ? "This will create a new file." : "這會建立新檔案。");
  const absolutePath = action.absoluteTargetPath || "";
  const pathMeta = absolutePath
    ? `${overwriteText} ${state.language === "en" ? "Full path:" : "完整路徑："} ${absolutePath}`
    : overwriteText;
  return `
    <div class="generated-action-card" data-action-id="${escapeHtml(String(action.id || ""))}">
      <div class="generated-action-header">
        <div>
          <div class="generated-action-path">${escapeHtml(action.targetPath || "")}</div>
          <div class="generated-action-meta">${escapeHtml(pathMeta)}</div>
        </div>
        <div class="actions generated-action-buttons">
          <button type="button" class="primary" data-action="confirm-generated">${escapeHtml(state.language === "en" ? "Confirm write" : "確認寫入")}</button>
          <button type="button" data-action="cancel-generated">${escapeHtml(state.language === "en" ? "Cancel" : "取消")}</button>
        </div>
      </div>
      <pre class="code-preview generated-file-preview">${escapeHtml(action.preview || "")}</pre>
    </div>
  `;
}

function renderGeneratedActionsHtml(actions) {
  const safeActions = Array.isArray(actions) ? actions.filter(Boolean) : [];
  return `
    <section class="transcript-tool-section">
      <div class="tool-card-head">
        <strong>${escapeHtml(safeActions.length > 1 ? (state.language === "en" ? "Generated file previews" : "生成檔案預覽") : (state.language === "en" ? "Generated file preview" : "生成檔案預覽"))}</strong>
        <span class="badge">${escapeHtml(String(safeActions.length))}</span>
      </div>
      ${safeActions.map((action) => renderGeneratedFileActionCard(action)).join("")}
    </section>
  `;
}

function renderGeneratedActionsTranscriptItem(item) {
  const data = item?.data || {};
  return renderGeneratedActionsHtml(data.pendingActions || (data.pendingAction ? [data.pendingAction] : []));
}

function removeGeneratedActionCard(actionId) {
  const card = elements.chatLog?.querySelector(`[data-action-id="${CSS.escape(String(actionId || ""))}"]`);
  card?.remove();
  if (!elements.chatLog?.querySelector(".generated-action-card")) {
    elements.pendingActionPanel?.classList.add("hidden");
    if (elements.pendingActionPanel) elements.pendingActionPanel.innerHTML = "";
  }
}

async function confirmGeneratedFile(actionId) {
  try {
    const data = await requestJson(`/api/files/generate/${encodeURIComponent(actionId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    removeGeneratedActionCard(actionId);
    setStatus(state.language === "en" ? "File written" : "檔案已寫入");
    await loadFileTree({ query: elements.fileTreeSearch?.value || "" });
    const writtenPath = data.path || data.absoluteTargetPath || data.targetPath || "";
    const sizeText = Number.isFinite(Number(data.sizeBytes)) && Number(data.sizeBytes) > 0
      ? ` (${Number(data.sizeBytes)} bytes)`
      : "";
    appendMessage("assistant", `${state.language === "en" ? "File written:" : "已寫入檔案："} ${writtenPath}${sizeText}`);
  } catch (error) {
    showError(normalizeError(error, "FILE_GENERATION_CONFIRM_FAILED", t("errors.fileGenerationFailed")));
  }
}

async function cancelGeneratedFile(actionId) {
  try {
    await requestJson(`/api/files/generate/${encodeURIComponent(actionId)}/cancel`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    removeGeneratedActionCard(actionId);
    setStatus(state.language === "en" ? "File generation cancelled" : "已取消檔案生成");
  } catch (error) {
    showError(normalizeError(error, "FILE_GENERATION_CANCEL_FAILED", t("errors.fileGenerationFailed")));
  }
}

function resetProjectViews(message = t("hints.initialSummary")) {
  state.summaryRaw = message;
  elements.projectSummary.textContent = message;
  clearTimeout(state.pinSyncTimer);
  state.pinSyncTimer = null;
  state.pinSyncRollback = null;
  state.pinSyncRequestId = 0;
  state.pinnedFiles = new Set();
  state.lastContextCoverage = null;
  renderPendingEdit(null);
  if (elements.structurePanel) {
    elements.structurePanel.classList.add("hidden");
    elements.structurePanel.innerHTML = "";
  }
  renderContextCoverage(null);
  renderTree([]);
}

async function pickFolder() {
  clearError();
  setStatus(t("statuses.openingFolder"), true);
  try {
    const data = await requestJson("/api/pick-folder", {
      method: "POST",
      body: JSON.stringify({}),
    });
    if (!data.canceled && data.path) {
      elements.projectPath.value = data.path;
    }
    setStatus(state.uiState === "ready" ? t("statuses.ready") : t("statuses.idle"));
  } catch (error) {
    setStatus(t("statuses.pickFolderFailed"));
    showError(normalizeError(error, "PICK_FOLDER_FAILED", t("errors.pickFolderFailed")));
  }
}

async function pollTask(taskId, kind) {
  state.currentTaskId = taskId;
  state.currentTaskKind = kind;
  const title = kind === "redownload-model" ? "正在重新下載模型" : "正在開啟專案";

  while (true) {
    const task = await requestJson(`/api/tasks/${taskId}`);
    renderProgress(task.progress || 0, buildProgressLabel(task), title, task);

    if (task.status === "completed") {
      state.currentTaskId = null;
      state.currentTaskKind = null;
      if (kind === "open-project") {
        clearError();
        setUiState("ready");
        await refreshStatus();
        setStatus(t("statuses.ready"));
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
    showError({ code: "PROJECT_PATH_INVALID", message: t("errors.projectPathInvalid"), details: "" });
    return;
  }

  clearError();
  clearChatImage({ silent: true });
  resetProjectViews(t("statuses.opening"));
  elements.chatLog.innerHTML = "";
  setUiState("opening");
  setStatus(t("statuses.opening"), true);
  renderProgress(0, "建立背景任務", t("progress.openTitle"));

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
    setStatus(t("statuses.openFailed"));
    showError(normalizeError(error, "OPEN_PROJECT_FAILED", t("errors.openProjectFailed")));
  }
}

async function redownloadModel() {
  const modelKey = state.lastError?.modelKey || elements.modelKey.value || "gemma4";
  clearError();
  setUiState("error");
  setStatus(t("statuses.redownloading"), true);
  renderProgress(0, "建立背景任務", t("progress.redownloadTitle"));
  try {
    const data = await requestJson("/api/models/redownload", {
      method: "POST",
      body: JSON.stringify({ modelKey }),
    });
    await pollTask(data.taskId, "redownload-model");
  } catch (error) {
    setStatus(t("statuses.modelRedownloadFailed"));
    showError(normalizeError(error, "MODEL_DOWNLOAD_FAILED", t("errors.modelDownloadFailed")));
  }
}

const STRUCTURE_CATEGORY_ORDER = [
  "entrypoints",
  "projectConfigs",
  "sourceFiles",
  "uiFiles",
  "assetFiles",
  "testFiles",
  "generatedFiles",
  "ignoredBuildOutputs",
];

function structureCategoryLabel(key) {
  return t(`structure.${key}`);
}

function renderPathList(paths, limit = 8) {
  const safePaths = Array.isArray(paths) ? paths.filter(Boolean) : [];
  if (!safePaths.length) {
    return `<div class="structure-empty">${escapeHtml(t("hints.structureNoItems"))}</div>`;
  }
  const visible = safePaths.slice(0, limit);
  const more = safePaths.length - visible.length;
  return `
    <ul class="structure-path-list">
      ${visible.map((path) => `<li><button type="button" class="structure-path" data-path="${escapeHtml(path)}">${escapeHtml(path)}</button></li>`).join("")}
      ${more > 0 ? `<li class="meta">${escapeHtml(t("summary.moreCount", more))}</li>` : ""}
    </ul>
  `;
}

function renderProjectStructure(data) {
  if (!elements.structurePanel) return;
  elements.structurePanel.classList.add("hidden");
  elements.structurePanel.innerHTML = "";
  appendToolCard({
    id: data?.transcriptItem?.id || "",
    kind: "tool-structure",
    title: t("structure.title"),
    html: renderStructureTranscriptHtml(data),
    item: data?.transcriptItem || null,
  });
  bindTranscriptInteractions(elements.chatLog);
}

function renderStructureTranscriptItem(item) {
  return renderStructureTranscriptHtml(item?.data?.structure || {});
}

function renderStructureTranscriptHtml(data) {
  const categories = data?.categories || {};
  const recommendedPins = Array.isArray(data?.recommendedPins) ? data.recommendedPins : [];
  const totalFiles = data?.counts?.totalFiles ?? 0;
  const categoryCards = STRUCTURE_CATEGORY_ORDER.map((key) => {
    const paths = Array.isArray(categories[key]) ? categories[key] : [];
    return `
      <section class="structure-card">
        <div class="structure-card-head">
          <strong>${escapeHtml(structureCategoryLabel(key))}</strong>
          <span class="badge">${paths.length}</span>
        </div>
        ${renderPathList(paths)}
      </section>
    `;
  }).join("");
  return `
    <div class="structure-head">
      <div>
        <strong>${escapeHtml(t("structure.title"))}</strong>
        <div class="meta">${escapeHtml(t("structure.summary"))} · ${escapeHtml(t("structure.totalFiles"))}: ${escapeHtml(String(totalFiles))}</div>
      </div>
      <button type="button" class="primary" data-structure-pin data-paths="${escapeHtml(JSON.stringify(recommendedPins))}" ${recommendedPins.length ? "" : "disabled"}>${escapeHtml(t("structure.pinRecommended"))}</button>
    </div>
    <div class="structure-recommended">
      <strong>${escapeHtml(t("structure.recommendedPins"))}</strong>
      <div class="meta">${escapeHtml(t("hints.structurePinHint"))}</div>
      ${renderPathList(recommendedPins, 12)}
    </div>
    <div class="structure-grid">${categoryCards}</div>
  `;
}

function pinStructureRecommendedFiles(paths) {
  const safePaths = Array.isArray(paths) ? paths.filter(Boolean) : [];
  if (!safePaths.length) return;
  const rollback = new Set(state.pinnedFiles);
  safePaths.forEach((path) => state.pinnedFiles.add(path));
  elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
  renderTree(state.tree, state.virtualTree.total || state.tree.length);
  schedulePinnedFilesSync(rollback);
  setStatus(t("structure.pinnedRecommended", safePaths.length));
}

async function analyzeProject() {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  clearError();
  setStatus(t("statuses.analyzing"), true);
  try {
    const data = await requestJson("/api/project/structure");
    renderProjectStructure(data);
    setStatus(t("statuses.analyzeDone"));
  } catch (error) {
    setStatus(t("statuses.analyzeFailed"));
    showError(normalizeError(error, "PROJECT_STRUCTURE_FAILED", t("errors.analyzeFailed")));
  }
}

function actionRiskLabel(action) {
  const high = String(action?.risk || "") === "high";
  if (state.language === "en") return high ? "high risk" : "review";
  return high ? "高風險" : "需確認";
}

function renderEditSnippetBlock(label, value) {
  const text = String(value || "").trim();
  return `
    <div class="edit-snippet-block">
      <div class="meta">${escapeHtml(label)}</div>
      <pre class="diff-block">${escapeHtml(text || (state.language === "en" ? "Not provided." : "未提供。"))}</pre>
    </div>
  `;
}

function renderEditDetailHtml(detail, fallbackAction = null) {
  const before = detail?.beforeSnippet || detail?.before || "";
  const after = detail?.afterSnippet || detail?.after || "";
  const diff = detail?.diffWindow || detail?.diff || fallbackAction?.diffWindow || fallbackAction?.diff || "";
  const notes = Array.isArray(detail?.notes) ? detail.notes.filter(Boolean) : [];
  return `
    <div class="edit-detail-grid">
      <div><strong>${escapeHtml(state.language === "en" ? "Location" : "修改位置")}：</strong>${escapeHtml(detail?.location || (state.language === "en" ? "Not provided" : "未提供"))}</div>
      <div><strong>${escapeHtml(state.language === "en" ? "Target" : "命中函式/區塊")}：</strong>${escapeHtml(detail?.target || (state.language === "en" ? "Not provided" : "未提供"))}</div>
      <div><strong>${escapeHtml(state.language === "en" ? "Reason" : "原因")}：</strong>${escapeHtml(detail?.reason || detail?.whyHere || fallbackAction?.summary || (state.language === "en" ? "Not provided" : "未提供"))}</div>
    </div>
    ${renderEditSnippetBlock(state.language === "en" ? "Original snippet" : "建議替換前片段", before)}
    ${renderEditSnippetBlock(state.language === "en" ? "Modified snippet" : "建議替換後片段", after)}
    ${renderEditSnippetBlock("Diff", diff)}
    ${notes.length ? `<div class="meta">${escapeHtml(state.language === "en" ? "Notes" : "補充說明")}：${escapeHtml(notes.join("；"))}</div>` : ""}
  `;
}

function renderEditPlanHtml(plan) {
  const actions = Array.isArray(plan?.actions) ? plan.actions : [];
  const edits = Array.isArray(plan?.edits) ? plan.edits : [];
  const suggestions = Array.isArray(plan?.suggestions) ? plan.suggestions : [];
  const actionHtml = actions.length
    ? actions.map((action) => {
      const detail = edits.find((item) => item.path === action.path) || null;
      return `
      <section class="edit-action-card">
        <div class="tool-card-head">
          <strong>${escapeHtml(action.kind || "action")}</strong>
          <span class="badge">${escapeHtml(actionRiskLabel(action))}</span>
        </div>
        <div class="tool-card-body">
          <div><strong>${escapeHtml(state.language === "en" ? "Path" : "檔案")}：</strong>${escapeHtml(action.path || action.command || "")}</div>
          ${action.targetPath ? `<div><strong>${escapeHtml(state.language === "en" ? "Target" : "目標")}：</strong>${escapeHtml(action.targetPath)}</div>` : ""}
          ${renderEditDetailHtml(detail || {}, action)}
        </div>
      </section>
    `;
    }).join("")
    : suggestions.length
      ? suggestions.map((item) => `
        <section class="edit-action-card">
          <div class="tool-card-head">
            <strong>${escapeHtml(state.language === "en" ? "Manual suggestion" : "手動修改建議")}</strong>
            <span class="badge">${escapeHtml(state.language === "en" ? "advisory" : "文字模式")}</span>
          </div>
          <div class="tool-card-body">
            <div><strong>${escapeHtml(state.language === "en" ? "Path" : "檔案")}：</strong>${escapeHtml(item.path || "")}</div>
            ${renderEditDetailHtml(item, null)}
          </div>
        </section>
      `).join("")
      : `<div class="tool-card-body">${escapeHtml(state.language === "en" ? "No directly applicable file actions. Review the advisory text and refine the request." : "沒有可直接套用的檔案操作。請查看文字建議後補充需求。")}</div>`;
  const canApply = actions.some((action) => action.status === "pending");
  return `
    <section class="transcript-tool-section edit-plan-status">
      <div class="tool-card-head">
        <strong>${escapeHtml(state.language === "en" ? "Edit plan" : "修改計畫")}</strong>
        <span class="badge">${escapeHtml(plan?.mode || "precise")}</span>
      </div>
      <div class="tool-card-body">
        <p>${escapeHtml(plan?.summary || "")}</p>
        ${plan?.failureReason ? `<p>${escapeHtml(plan.failureReason)}</p>` : ""}
      </div>
      <div class="edit-action-list">${actionHtml}</div>
      <div class="tool-action-row">
        ${canApply
          ? `<button type="button" class="primary" data-edit-apply>${escapeHtml(t("buttons.applyEdit"))}</button>`
          : `<button type="button" disabled>${escapeHtml(state.language === "en" ? "No applicable action" : "沒有可套用操作")}</button>`}
        <button type="button" data-git-diff>${escapeHtml(t("buttons.gitDiff"))}</button>
        <button type="button" data-edit-discard>${escapeHtml(t("buttons.discardEdit"))}</button>
      </div>
    </section>
  `;
}

function renderEditResultTranscriptItem(item) {
  const result = item?.data?.result || {};
  const files = Array.isArray(result.changedFiles) ? result.changedFiles : [];
  const pre = result.preEditCommit || result.commit || "";
  return `
    <section class="transcript-tool-section edit-plan-status">
      <div class="tool-card-head">
        <strong>${escapeHtml(item?.title || (state.language === "en" ? "Edit result" : "修改結果"))}</strong>
        <span class="badge">${escapeHtml(result.failed ? (state.language === "en" ? "failed" : "失敗") : (result.restored ? (state.language === "en" ? "restored" : "已復原") : (state.language === "en" ? "applied" : "已套用")))}</span>
      </div>
      <div class="tool-card-body">
        ${result.error ? `<div>${escapeHtml(result.error)}</div>` : ""}
        ${result.preEditCommit ? `<div>pre-edit: <code>${escapeHtml(String(result.preEditCommit).slice(0, 12))}</code></div>` : ""}
        ${result.postEditCommit ? `<div>post-edit: <code>${escapeHtml(String(result.postEditCommit).slice(0, 12))}</code></div>` : ""}
        ${files.length ? `<div>${escapeHtml(state.language === "en" ? "Changed files" : "異動檔案")}：${escapeHtml(files.join(", "))}</div>` : ""}
        ${result.diffStat ? `<pre class="diff-block">${escapeHtml(result.diffStat)}</pre>` : ""}
      </div>
      <div class="tool-action-row">
        ${result.preEditCommit ? `<button type="button" data-git-diff="${escapeHtml(result.preEditCommit)}">${escapeHtml(t("buttons.gitDiff"))}</button>` : ""}
        ${pre ? `<button type="button" class="danger" data-git-restore="${escapeHtml(pre)}">${escapeHtml(t("buttons.restoreEdit"))}</button>` : ""}
      </div>
    </section>
  `;
}

function renderEditPlan(plan, { append = true } = {}) {
  state.pendingEdit = plan || null;
  updateChatPlaceholder();
  if (append && plan) {
    appendToolCard({
      kind: "action-edit-plan",
      title: state.language === "en" ? "Edit plan" : "修改計畫",
      html: renderEditPlanHtml(plan),
    });
  }
}

async function generateEditPlan() {
  const message = elements.chatInput.value.trim();
  if (!message) {
    showError({ code: "EDIT_PLAN_FAILED", message: state.language === "en" ? "Please enter a change request first." : "請先輸入修改需求。", details: "" });
    return;
  }
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  clearError();
  appendMessage("user", message);
  elements.chatInput.value = "";
  setStatus(state.language === "en" ? "Generating edit suggestion" : "正在產生修改建議", true);
  setAiBusy(true, state.language === "en" ? "AI is generating an edit plan" : "AI 正在產生修改建議");
  try {
    const data = await requestJson("/api/edit/plan", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderEditPlan(data.plan, { append: true });
    const modeLabel = data.plan.mode === "advisory" ? (state.language === "en" ? "advisory" : "文字模式") : (state.language === "en" ? "precise" : "精準模式");
    appendMessage("assistant", `${state.language === "en" ? "Edit suggestion generated" : "已產生修改建議"} (${modeLabel})\n\n${buildPendingEditText(data.plan)}`);
    setStatus(state.language === "en" ? "Edit suggestion ready" : "修改建議已產生");
    setUiState("ready");
  } catch (error) {
    setStatus(state.language === "en" ? "Edit suggestion failed" : "產生建議失敗");
    showError(normalizeError(error, "EDIT_PLAN_FAILED", state.language === "en" ? "Failed to generate edit suggestion." : "產生修改建議失敗。"));
  } finally {
    setAiBusy(false);
  }
}

async function applyEditPlan() {
  if (!state.pendingEdit) return;
  clearError();
  setStatus(state.language === "en" ? "Applying edit" : "正在套用修改", true);
  try {
    const actionIds = (state.pendingEdit.actions || []).filter((action) => action.status === "pending").map((action) => action.id);
    const data = await requestJson("/api/edit/apply", {
      method: "POST",
      body: JSON.stringify({ actionIds }),
    });
    renderEditPlan(data.pendingEdit || null, { append: false });
    appendToolCard({
      kind: "action-edit-apply",
      title: state.language === "en" ? "Edit applied" : "修改已套用",
      html: renderEditResultTranscriptItem({ title: state.language === "en" ? "Edit applied" : "修改已套用", data: { result: data.result } }),
    });
    setStatus(state.language === "en" ? "Edit applied" : "修改已套用");
  } catch (error) {
    setStatus(state.language === "en" ? "Apply failed" : "套用失敗");
    const normalized = normalizeError(error, "EDIT_APPLY_FAILED", state.language === "en" ? "Failed to apply edit." : "套用修改失敗。");
    if (normalized.pendingEdit) {
      state.pendingEdit = normalized.pendingEdit;
    }
    if (normalized.result) {
      appendToolCard({
        kind: "action-edit-apply",
        title: state.language === "en" ? "Apply failed" : "套用失敗",
        html: renderEditResultTranscriptItem({ title: state.language === "en" ? "Apply failed" : "套用失敗", data: { result: normalized.result } }),
      });
    }
    showError(normalized);
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
    setStatus(state.language === "en" ? "Cleared edit suggestion" : "已清除修改建議");
    setUiState("ready");
  } catch (error) {
    showError(normalizeError(error, "DISCARD_EDIT_FAILED", state.language === "en" ? "Failed to clear edit suggestion." : "清除修改建議失敗。"));
  }
}

async function showGitDiff(base = "") {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  clearError();
  setStatus(state.language === "en" ? "Loading Git diff" : "正在讀取 Git diff", true);
  try {
    const suffix = base ? `?base=${encodeURIComponent(base)}` : "";
    const data = await requestJson(`/api/git/diff${suffix}`);
    appendToolCard({
      kind: "tool-git-diff",
      title: "Git diff",
      html: `
        <section class="transcript-tool-section edit-plan-status">
          <div class="tool-card-head"><strong>Git diff</strong><span class="badge">${escapeHtml((data.changedFiles || []).length)} files</span></div>
          <div class="tool-card-body">
            ${(data.changedFiles || []).length ? `<div>${escapeHtml((data.changedFiles || []).join(", "))}</div>` : `<div>${escapeHtml(state.language === "en" ? "No changes." : "沒有異動。")}</div>`}
            <pre class="diff-block">${escapeHtml(data.diff || data.stat || "")}</pre>
          </div>
        </section>
      `,
    });
    setStatus(state.language === "en" ? "Git diff loaded" : "Git diff 已載入");
  } catch (error) {
    setStatus(state.language === "en" ? "Git diff failed" : "Git diff 失敗");
    showError(normalizeError(error, "GIT_DIFF_FAILED", state.language === "en" ? "Failed to load Git diff." : "讀取 Git diff 失敗。"));
  }
}

async function createGitCheckpoint() {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  clearError();
  setStatus(state.language === "en" ? "Creating checkpoint" : "正在建立 checkpoint", true);
  try {
    const data = await requestJson("/api/git/checkpoint", {
      method: "POST",
      body: JSON.stringify({ label: "manual" }),
    });
    appendToolCard({
      kind: "tool-git-checkpoint",
      title: "Git checkpoint",
      html: `<section class="transcript-tool-section edit-plan-status"><div class="tool-card-body">checkpoint: <code>${escapeHtml(data.checkpoint?.shortCommit || "")}</code><br>${escapeHtml(data.checkpoint?.message || "")}</div></section>`,
    });
    setStatus(state.language === "en" ? "Checkpoint created" : "checkpoint 已建立");
  } catch (error) {
    setStatus(state.language === "en" ? "Checkpoint failed" : "checkpoint 失敗");
    showError(normalizeError(error, "GIT_CHECKPOINT_FAILED", state.language === "en" ? "Failed to create checkpoint." : "建立 checkpoint 失敗。"));
  }
}

async function restoreEditCheckpoint(checkpoint) {
  if (!checkpoint) return;
  const ok = window.confirm(state.language === "en" ? "Restore this edit? Current changes after the checkpoint will be reset." : "確定復原這次修改？checkpoint 之後的變更會被重設。");
  if (!ok) return;
  clearError();
  setStatus(state.language === "en" ? "Restoring edit" : "正在復原修改", true);
  try {
    const data = await requestJson("/api/git/restore", {
      method: "POST",
      body: JSON.stringify({ checkpoint }),
    });
    renderEditPlan(null, { append: false });
    appendToolCard({
      kind: "action-edit-restore",
      title: state.language === "en" ? "Edit restored" : "已復原修改",
      html: renderEditResultTranscriptItem({ title: state.language === "en" ? "Edit restored" : "已復原修改", data: { result: data.result } }),
    });
    setStatus(state.language === "en" ? "Edit restored" : "已復原修改");
  } catch (error) {
    setStatus(state.language === "en" ? "Restore failed" : "復原失敗");
    showError(normalizeError(error, "GIT_RESTORE_FAILED", state.language === "en" ? "Failed to restore edit." : "復原修改失敗。"));
  }
}

function schedulePinnedFilesSync(rollback) {
  if (state.uiState !== "ready") {
    return;
  }
  if (!state.pinSyncRollback) {
    state.pinSyncRollback = rollback;
  }
  clearTimeout(state.pinSyncTimer);
  setStatus(t("statuses.updateContext"), true);
  state.pinSyncTimer = window.setTimeout(() => {
    syncPinnedFiles().catch(() => {});
  }, 200);
}

async function syncPinnedFiles() {
  if (state.uiState !== "ready") {
    return;
  }
  const rollback = state.pinSyncRollback ? new Set(state.pinSyncRollback) : new Set(state.pinnedFiles);
  state.pinSyncRollback = null;
  state.pinSyncTimer = null;
  const requestId = ++state.pinSyncRequestId;
  try {
    const data = await requestJson("/api/pin-files", {
      method: "POST",
      body: JSON.stringify({ files: [...state.pinnedFiles] }),
    });
    if (requestId !== state.pinSyncRequestId) {
      return;
    }
    setPinnedFiles(data.pinnedFiles || []);
    setStatus(t("statuses.appliedPins", state.pinnedFiles.size));
  } catch (error) {
    if (requestId !== state.pinSyncRequestId) {
      return;
    }
    state.pinnedFiles = rollback;
    elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
    renderTree(state.tree);
    setStatus(t("statuses.updateFailed"));
    showError(normalizeError(error, "PIN_FILES_FAILED", t("errors.pinFilesFailed")));
  }
}

async function sendChat(event) {
  event.preventDefault();
  const message = elements.chatInput.value.trim();
  const attachments = state.chatAttachments || [];
  if (!message && !attachments.length) {
    showError({ code: "CHAT_FAILED", message: t("errors.emptyChat"), details: "" });
    return;
  }
  clearError();
  startChatAutoScroll();
  appendMessage("user", message || t("hints.imageAttachedHint"), attachments);
  const selectedModelKey = elements.modelKey.value || state.modelKey;
  const liveTarget = appendLiveMessage("assistant", "", [], { modelKey: selectedModelKey, modelName: getModelLabel(selectedModelKey) });
  elements.chatInput.value = "";
  setStatus(t("statuses.thinking"), true);
  setAiBusy(true, t("labels.aiBusy"));
  let completed = false;
  try {
    await streamChat({
      message,
      modelKey: selectedModelKey,
      threadId: state.activeThreadId || "",
      attachmentIds: attachments.map((entry) => entry.id).filter(Boolean),
    }, (eventName, data) => {
      if (eventName === "context") {
        renderContextCoverage(data.contextCoverage || null, { appendToTranscript: true });
      } else if (eventName === "model") {
        if (liveTarget.role && data.modelName) {
          liveTarget.role.textContent = data.modelName;
        }
      } else if (eventName === "reasoning") {
        appendLiveReasoning(liveTarget, data.text || "");
      } else if (eventName === "continuation") {
        appendLiveText(liveTarget.content, `\n\n${data.text || (state.language === "en" ? "The answer was long, continuing automatically." : "內容過長，已自動續寫。")}\n\n`);
      } else if (eventName === "attachment_fallback") {
        const kinds = Array.isArray(data.fallbackKinds) ? data.fallbackKinds.join(", ") : "";
        const reason = String(data.reason || "").trim();
        const text = state.language === "en"
          ? `\n\nAttachment native input was rejected; retried with text/metadata fallback${kinds ? ` (${kinds})` : ""}${reason ? `。Reason: ${reason}` : ""}.\n\n`
          : `\n\n原生附件輸入被模型服務拒絕，已改用文字/metadata fallback 重新送出${kinds ? `（${kinds}）` : ""}${reason ? `。原因：${reason}` : ""}。\n\n`;
        appendLiveText(liveTarget.content, text);
      } else if (eventName === "content") {
        appendLiveText(liveTarget.content, data.text || "");
      } else if (eventName === "generated_file_preview") {
        const actions = Array.isArray(data.pendingActions)
          ? data.pendingActions
          : (data.pendingAction ? [data.pendingAction] : []);
        renderGeneratedFileActions(actions);
        const countText = actions.length > 1
          ? (state.language === "en" ? `${actions.length} file previews are ready.` : `已準備 ${actions.length} 個檔案預覽。`)
          : (state.language === "en" ? "File preview is ready." : "檔案預覽已準備完成。");
        appendLiveText(
          liveTarget.content,
          `\n\n${countText}${state.language === "en" ? " Confirm the preview below before writing." : " 請在下方預覽確認後再寫入。"}\n`
        );
      } else if (eventName === "generated_file_error") {
        const normalized = normalizeError(data, "FILE_GENERATION_FAILED", t("errors.fileGenerationFailed"));
        appendLiveText(liveTarget.content, `\n\n${state.language === "en" ? "File preview failed:" : "檔案預覽建立失敗："} ${localizeError(normalized).message}\n`);
      } else if (eventName === "done") {
        completed = true;
        if (data.modelKey) {
          state.modelKey = data.modelKey;
          elements.modelKey.value = data.modelKey;
        }
        renderContextCoverage(data.contextCoverage || null);
      } else if (eventName === "error") {
        throw data;
      }
    });
    clearChatImage({ silent: true });
  } catch (error) {
    const normalized = normalizeError(error, "CHAT_FAILED", t("errors.chatFailed"));
    showError(normalized);
    renderContextCoverage(null);
    appendLiveText(liveTarget.content, `${state.language === "en" ? "Error:" : "發生錯誤："} ${localizeError(normalized).message}`);
  } finally {
    setAiBusy(false);
    setStatus(completed ? t("statuses.done") : t("statuses.chatFailed"));
  }
}

function clearChat() {
  requestJson("/api/reset-history", {
    method: "POST",
    body: JSON.stringify({}),
  })
    .then(() => {
      state.history = [];
      state.transcript = [];
      elements.chatLog.innerHTML = "";
      renderPendingEdit(null);
      renderContextCoverage(null);
      clearChatImage({ silent: true });
      setStatus(state.uiState === "ready" ? t("statuses.ready") : t("statuses.historyCleared"));
    })
    .catch((error) => showError(normalizeError(error, "RESET_HISTORY_FAILED", t("errors.resetHistoryFailed"))));
}
