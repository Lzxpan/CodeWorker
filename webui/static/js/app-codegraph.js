function codeGraphMatchedFiles(result = state.codeGraphLastResult) {
  const files = new Set();
  const explicit = Array.isArray(result?.matchedFiles) ? result.matchedFiles : [];
  explicit.forEach((path) => files.add(String(path)));
  const nodes = Array.isArray(result?.nodes) ? result.nodes : [];
  nodes.forEach((node) => {
    if (node?.path) files.add(String(node.path));
  });
  const edges = Array.isArray(result?.edges) ? result.edges : [];
  edges.forEach((edge) => {
    if (edge?.source?.path) files.add(String(edge.source.path));
    if (edge?.target?.path) files.add(String(edge.target.path));
  });
  return [...files].filter(Boolean);
}

function setCodeGraphButtonsBusy(isBusy) {
  if (elements.codeGraphUsePromptBtn) elements.codeGraphUsePromptBtn.disabled = isBusy;
  if (elements.codeGraphRebuildBtn) {
    elements.codeGraphRebuildBtn.disabled = isBusy;
    elements.codeGraphRebuildBtn.setAttribute("aria-busy", isBusy ? "true" : "false");
  }
}

function renderCodeGraphChips(values = []) {
  const chips = [...new Set((Array.isArray(values) ? values : []).map((item) => String(item || "").trim()).filter(Boolean))].slice(0, 8);
  if (!chips.length) return "";
  return `
    <div class="codegraph-chip-row" aria-label="${escapeHtml(state.language === "en" ? "CodeGraph query examples" : "CodeGraph 可查範例")}">
      <span class="meta">${escapeHtml(state.language === "en" ? "Try:" : "可查範例：")}</span>
      ${chips.map((item) => `<button type="button" class="codegraph-chip" data-codegraph-query="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")}
    </div>
  `;
}

function codeGraphSuggestions(source = null) {
  const values = [];
  const status = source?.status || source || state.codeGraphStatus || {};
  if (Array.isArray(source?.suggestions)) values.push(...source.suggestions);
  if (Array.isArray(status.sampleSymbols)) values.push(...status.sampleSymbols);
  if (Array.isArray(status.sampleFiles)) values.push(...status.sampleFiles);
  return [...new Set(values.map((item) => String(item || "").trim()).filter(Boolean))].slice(0, 8);
}

function codeGraphStatusItems(status = {}) {
  const ready = status.ready
    ? (state.language === "en" ? "ready" : "已就緒")
    : (state.language === "en" ? "not ready" : "尚未就緒");
  return [
    [state.language === "en" ? "Status" : "狀態", ready],
    [state.language === "en" ? "Files" : "indexed files", status.files ?? 0],
    [state.language === "en" ? "Symbols" : "symbols/nodes", status.nodeCount ?? status.nodes ?? 0],
    [state.language === "en" ? "Relationships" : "relationships/edges", status.edgeCount ?? status.edges ?? 0],
    [state.language === "en" ? "Unresolved" : "unresolved", status.unresolvedCount ?? status.unresolvedReferences ?? status.unresolved ?? 0],
    [state.language === "en" ? "Updated" : "最後重建", status.indexUpdatedAt || (state.language === "en" ? "unknown" : "未知")],
  ];
}

function renderCodeGraphStats(status = {}) {
  return `
    <div class="codegraph-stats">
      ${codeGraphStatusItems(status).map(([label, value]) => `
        <div class="codegraph-stat">
          <span class="meta">${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </div>
      `).join("")}
    </div>
    ${status.indexDir ? `<div class="codegraph-path">indexDir: ${escapeHtml(status.indexDir)}</div>` : ""}
  `;
}

function renderCodeGraphOperation(kind, title, details = []) {
  if (!elements.codeGraphResults) return;
  const safeDetails = Array.isArray(details) ? details.filter(Boolean) : [];
  elements.codeGraphResults.classList.add("hidden");
  const html = `
    <section class="codegraph-section">
      <div class="codegraph-result-head">
        <strong>${escapeHtml(title)}</strong>
        <span class="badge">${escapeHtml(kind)}</span>
      </div>
      ${safeDetails.length ? `<div class="codegraph-result-list">${safeDetails.map((detail) => `<div class="codegraph-path">${escapeHtml(detail)}</div>`).join("")}</div>` : ""}
    </section>
  `;
  elements.codeGraphResults.innerHTML = html;
  appendToolCard({
    id: "codegraph-live",
    kind: "tool-codegraph",
    title: "CodeGraph",
    html,
    replaceId: "codegraph-live",
  });
}

function renderCodeGraphError(error) {
  if (!elements.codeGraphResults) return;
  elements.codeGraphResults.classList.add("hidden");
  elements.codeGraphResults.classList.add("empty");
  const status = state.codeGraphStatus || {};
  const html = `
    <section class="codegraph-section">
      <div class="codegraph-result-head">
        <strong>${escapeHtml(t("errors.codeGraphFailed"))}</strong>
        <span class="badge">${escapeHtml(state.language === "en" ? "error" : "錯誤")}</span>
      </div>
      <div class="codegraph-path">${escapeHtml(error?.message || "")}</div>
      ${renderCodeGraphChips(codeGraphSuggestions(status))}
    </section>
  `;
  elements.codeGraphResults.innerHTML = html;
  appendToolCard({
    id: "codegraph-live",
    kind: "tool-codegraph",
    title: "CodeGraph",
    html,
    replaceId: "codegraph-live",
  });
  bindCodeGraphInteractions();
  bindTranscriptInteractions(elements.chatLog);
}

function renderCodeGraphStatusSummary(status, prefix = "") {
  const readyText = status?.ready
    ? (state.language === "en" ? "ready" : "已就緒")
    : (state.language === "en" ? "not ready" : "尚未就緒");
  const nodes = status?.nodeCount ?? status?.nodes ?? 0;
  const edges = status?.edgeCount ?? status?.edges ?? 0;
  const unresolved = status?.unresolvedCount ?? status?.unresolvedReferences ?? status?.unresolved ?? 0;
  const indexDir = status?.indexDir || "";
  const head = prefix ? `${prefix} · ${readyText}` : readyText;
  return [
    `${head}: nodes ${nodes}, edges ${edges}, unresolved ${unresolved}`,
    indexDir ? `indexDir: ${indexDir}` : "",
  ].filter(Boolean);
}

function renderCodeGraphStatusPanel(status = state.codeGraphStatus) {
  if (!elements.codeGraphResults || !status) return;
  state.codeGraphStatus = status;
  state.codeGraphLastResult = null;
  elements.codeGraphPinBtn.disabled = true;
  elements.codeGraphResults.classList.add("hidden");
  elements.codeGraphResults.classList.remove("empty");
  const title = status.ready
    ? (state.language === "en" ? "CodeGraph index is ready" : "CodeGraph index 已就緒")
    : (state.language === "en" ? "CodeGraph index is not ready" : "CodeGraph index 尚未就緒");
  elements.codeGraphResults.innerHTML = `
    <section class="codegraph-section">
      <div class="codegraph-result-head">
        <strong>${escapeHtml(title)}</strong>
        <span class="badge">${escapeHtml(status.ready ? (state.language === "en" ? "ready" : "可查詢") : (state.language === "en" ? "not ready" : "需重建"))}</span>
      </div>
      <div class="codegraph-help">${escapeHtml(t("hints.codeGraphEmpty"))}</div>
      ${renderCodeGraphStats(status)}
      ${renderCodeGraphChips(codeGraphSuggestions(status))}
      <div class="codegraph-next-step">${escapeHtml(t("hints.codeGraphPinDisabled"))}</div>
    </section>
  `;
  bindCodeGraphInteractions();
}

function renderCodeGraphRebuildSummary(rebuild = state.codeGraphLastRebuild) {
  if (!rebuild) return "";
  const graph = rebuild.codeGraph || {};
  const status = rebuild.status || {};
  const items = [
    [state.language === "en" ? "Files" : "files", rebuild.files ?? status.files ?? 0],
    [state.language === "en" ? "Chunks" : "chunks", rebuild.chunks ?? 0],
    [state.language === "en" ? "Symbols" : "nodes", graph.nodes ?? status.nodeCount ?? 0],
    [state.language === "en" ? "Relationships" : "edges", graph.edges ?? status.edgeCount ?? 0],
    [state.language === "en" ? "Unresolved" : "unresolved", graph.unresolvedReferences ?? status.unresolvedCount ?? 0],
    [state.language === "en" ? "Duration" : "耗時", `${Math.max(0, Math.round(Number(rebuild.durationMs || 0) / 1000))}s`],
  ];
  return `
    <section class="codegraph-section codegraph-rebuild-summary">
      <div class="codegraph-result-head">
        <strong>${escapeHtml(state.language === "en" ? "Rescan complete" : "重新掃描完成")}</strong>
        <span class="badge">${escapeHtml(rebuild.indexUpdatedAt || status.indexUpdatedAt || "")}</span>
      </div>
      <div class="codegraph-stats">
        ${items.map(([label, value]) => `
          <div class="codegraph-stat">
            <span class="meta">${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value))}</strong>
          </div>
        `).join("")}
      </div>
      ${(rebuild.indexDir || status.indexDir) ? `<div class="codegraph-path">indexDir: ${escapeHtml(rebuild.indexDir || status.indexDir)}</div>` : ""}
      ${renderCodeGraphChips(codeGraphSuggestions({ status, suggestions: rebuild.sampleSymbols || [] }))}
    </section>
  `;
}

function codeGraphQueryMessage(result, nodes, edges, matchedFiles) {
  const query = result?.query || "";
  if (!nodes.length && !edges.length) {
    return state.language === "en"
      ? `CodeGraph could not find "${query}" in the current project. Try one of the example chips, a symbol, a class/function name, or a file name.`
      : `CodeGraph 在目前專案找不到「${query}」。請改用下方範例、symbol、class/function 名稱或檔名。`;
  }
  return state.language === "en"
    ? `CodeGraph found ${nodes.length} symbol(s), ${edges.length} relationship(s), and ${matchedFiles.length} matched file(s). It has not asked AI yet.`
    : `CodeGraph 找到 ${nodes.length} 個 symbol、${edges.length} 個關聯、${matchedFiles.length} 個命中文件；這一步還沒有送給 AI。`;
}

function renderCodeGraphResultHtml(result = null, options = {}) {
  if (!result) return "";
  const nodes = Array.isArray(result.nodes) ? result.nodes : [];
  const edges = Array.isArray(result.edges) ? result.edges : [];
  const matchedFiles = codeGraphMatchedFiles(result);
  const status = result.status || state.codeGraphStatus || {};
  const rebuildHtml = options.rebuild ? renderCodeGraphRebuildSummary(options.rebuild) : "";
  const queryMessage = codeGraphQueryMessage(result, nodes, edges, matchedFiles);
  if (!nodes.length && !edges.length) {
    return `
      ${rebuildHtml}
      <section class="codegraph-section">
        <div class="codegraph-result-head">
          <strong>${escapeHtml(queryMessage)}</strong>
          <span class="badge">${escapeHtml(state.language === "en" ? "no match" : "無命中")}</span>
        </div>
        <div class="codegraph-help">${escapeHtml(t("hints.codeGraphNoMatches"))}</div>
        ${renderCodeGraphStats(status)}
        ${renderCodeGraphChips(codeGraphSuggestions(result))}
      </section>
    `;
  }
  const summary = state.language === "en"
    ? `${nodes.length} symbol(s), ${edges.length} relationship(s), ${matchedFiles.length} matched file(s)`
    : `${nodes.length} 個 symbol、${edges.length} 個關聯、${matchedFiles.length} 個命中文件`;
  const nodeHtml = nodes.slice(0, 10).map((node) => `
    <button type="button" class="codegraph-node" data-path="${escapeHtml(node.path || "")}">
      <span class="codegraph-node-kind">${escapeHtml(node.kind || "symbol")}</span>
      <span>
        <strong>${escapeHtml(node.name || "")}</strong>
        <span class="codegraph-path">${escapeHtml(node.path || "")}:${escapeHtml(node.lineStart || 1)}</span>
      </span>
    </button>
  `).join("");
  const edgeHtml = edges.slice(0, 8).map((edge) => {
    const source = edge.source || {};
    const target = edge.target || {};
    return `<div class="codegraph-path">${escapeHtml(source.name || "")} --${escapeHtml(edge.kind || "")}--> ${escapeHtml(target.name || "")}</div>`;
  }).join("");
  const matchedHtml = matchedFiles.slice(0, 12).map((path) => `<button type="button" class="codegraph-file" data-path="${escapeHtml(path)}">${escapeHtml(path)}</button>`).join("");
  return `
    ${rebuildHtml}
    <section class="codegraph-section">
      <div class="codegraph-result-head">
        <strong>${escapeHtml(summary)}</strong>
        <span class="meta">${escapeHtml(t("hints.codeGraphUsingChatInput"))}: ${escapeHtml(result.query || "")}</span>
      </div>
      <div class="codegraph-help">${escapeHtml(queryMessage)}</div>
      ${renderCodeGraphStats(status)}
      <div class="codegraph-subsection">
        <strong>${escapeHtml(state.language === "en" ? "Matched symbols" : "命中 symbols")}</strong>
        <div class="codegraph-result-list">${nodeHtml}</div>
      </div>
      <div class="codegraph-subsection">
        <strong>${escapeHtml(state.language === "en" ? "Relationships" : "關聯 relationships")}</strong>
        <div class="codegraph-result-list">${edgeHtml || `<span class="meta">${escapeHtml(state.language === "en" ? "No relationships found for these symbols." : "這次命中的 symbol 沒有額外關聯。")}</span>`}</div>
      </div>
      <div class="codegraph-subsection">
        <strong>${escapeHtml(state.language === "en" ? "Matched files" : "命中文件")}</strong>
        <div class="codegraph-file-list">${matchedHtml}</div>
      </div>
      <div class="codegraph-next-step">${escapeHtml(t("hints.codeGraphNextStep"))}</div>
    </section>
  `;
}

function renderCodeGraphTranscriptItem(item) {
  const data = item?.data || {};
  const operation = data.operation || "";
  const result = data.result || {};
  if (operation === "rebuild") {
    return renderCodeGraphRebuildSummary(result);
  }
  if (operation === "query") {
    return renderCodeGraphResultHtml(result);
  }
  return `<section class="codegraph-section"><div class="codegraph-help">${escapeHtml(item?.content || "")}</div></section>`;
}

function renderCodeGraphResults(result = null, options = {}) {
  if (!elements.codeGraphResults) return;
  state.codeGraphLastResult = result;
  elements.codeGraphPinBtn.disabled = !codeGraphMatchedFiles(result).length;
  if (!result) {
    renderCodeGraphStatusPanel(state.codeGraphStatus);
    return;
  }
  const status = result.status || state.codeGraphStatus || {};
  state.codeGraphStatus = status;
  elements.codeGraphResults.classList.add("hidden");
  const html = renderCodeGraphResultHtml(result, options);
  elements.codeGraphResults.innerHTML = html;
  appendToolCard({
    id: result.transcriptItem?.id || "",
    kind: "tool-codegraph",
    title: state.language === "en" ? "CodeGraph query" : "CodeGraph 查詢",
    html,
    item: result.transcriptItem || null,
    replaceId: "codegraph-live",
  });
  bindCodeGraphInteractions();
  bindTranscriptInteractions(elements.chatLog);
}

function bindCodeGraphInteractions() {
  const root = elements.codeGraphResults;
  if (!root) return;
  root.querySelectorAll("[data-codegraph-query]").forEach((button) => {
    button.addEventListener("click", () => {
      const query = button.dataset.codegraphQuery || "";
      if (!query) return;
      elements.chatInput.value = query;
      queryCodeGraph().catch((error) => showError(normalizeError(error, "CODEGRAPH_QUERY_FAILED", t("errors.codeGraphFailed"))));
    });
  });
  root.querySelectorAll(".codegraph-node, .codegraph-file").forEach((button) => {
    button.addEventListener("click", () => {
      const path = button.dataset.path || "";
      if (!path) return;
      elements.fileTreeSearch.value = path;
      loadFileTree({ query: path, offset: 0, limit: 500 }).catch((error) => {
        showError(normalizeError(error, "FILE_TREE_FAILED", t("errors.fileTreeFailed")));
      });
    });
  });
}

async function loadCodeGraphStatus() {
  if (state.uiState !== "ready") return;
  try {
    const status = await requestJson("/api/codegraph/status");
    renderCodeGraphStatusPanel(status);
    if (status.ready) {
      setStatus(t("statuses.codeGraphReady"));
    }
  } catch (error) {
    renderCodeGraphError(error);
  }
}

async function requestCodeGraphQuery(query) {
  return requestJson("/api/codegraph/query", {
    method: "POST",
    body: JSON.stringify({ query, limit: 8 }),
  });
}

async function queryCodeGraph() {
  const query = elements.chatInput.value.trim();
  if (!query) {
    renderCodeGraphStatusPanel(state.codeGraphStatus);
    showError({ code: "CODEGRAPH_QUERY_FAILED", message: t("errors.codeGraphQueryRequired"), details: "" });
    return;
  }
  setStatus(t("statuses.codeGraphQuerying"), true);
  setCodeGraphButtonsBusy(true);
  renderCodeGraphOperation(
    state.language === "en" ? "querying" : "查詢中",
    t("statuses.codeGraphQuerying"),
    [t("hints.codeGraphUsingChatInput") + ": " + query]
  );
  try {
    const data = await requestCodeGraphQuery(query);
    renderCodeGraphResults(data);
    setStatus(t("statuses.codeGraphDone"));
  } catch (error) {
    renderCodeGraphError(error);
    showError(normalizeError(error, "CODEGRAPH_QUERY_FAILED", t("errors.codeGraphFailed")));
    setStatus(t("errors.codeGraphFailed"));
  } finally {
    setCodeGraphButtonsBusy(false);
  }
}

function normalizeRebuildStatus(rebuild = {}) {
  const graph = rebuild.codeGraph || {};
  return {
    ready: true,
    indexDir: rebuild.indexDir || "",
    indexUpdatedAt: rebuild.indexUpdatedAt || "",
    files: rebuild.files ?? 0,
    nodeCount: graph.nodeCount ?? graph.nodes ?? 0,
    edgeCount: graph.edgeCount ?? graph.edges ?? 0,
    unresolvedCount: graph.unresolvedCount ?? graph.unresolvedReferences ?? 0,
    sampleSymbols: rebuild.sampleSymbols || [],
    sampleFiles: rebuild.sampleFiles || [],
  };
}

async function rebuildCodeGraphIndex() {
  if (state.uiState !== "ready") {
    renderCodeGraphStatusPanel(state.codeGraphStatus);
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  const query = elements.chatInput.value.trim();
  setStatus(t("statuses.codeGraphRebuilding"), true);
  setCodeGraphButtonsBusy(true);
  renderCodeGraphOperation(
    state.language === "en" ? "rescanning" : "重新掃描中",
    t("statuses.codeGraphRebuilding"),
    [state.language === "en" ? "Rebuilding both RAG and CodeGraph indexes." : "正在重建 RAG + CodeGraph index。"]
  );
  try {
    const rebuild = await requestJson("/api/index/rebuild", { method: "POST", body: JSON.stringify({}) });
    const status = normalizeRebuildStatus(rebuild);
    rebuild.status = status;
    state.codeGraphLastRebuild = rebuild;
    state.codeGraphStatus = status;
    if (query) {
      const rebuildHtml = renderCodeGraphRebuildSummary(rebuild);
      appendToolCard({
        id: rebuild.transcriptItem?.id || "",
        kind: "tool-codegraph",
        title: state.language === "en" ? "CodeGraph rescan" : "重新掃描索引",
        html: rebuildHtml,
        item: rebuild.transcriptItem || null,
        replaceId: "codegraph-live",
      });
      const data = await requestCodeGraphQuery(query);
      renderCodeGraphResults(data);
      setStatus(t("statuses.codeGraphDone"));
    } else {
      const html = renderCodeGraphRebuildSummary(rebuild);
      elements.codeGraphResults.classList.add("hidden");
      elements.codeGraphResults.innerHTML = html;
      appendToolCard({
        id: rebuild.transcriptItem?.id || "",
        kind: "tool-codegraph",
        title: state.language === "en" ? "CodeGraph rescan" : "重新掃描索引",
        html,
        item: rebuild.transcriptItem || null,
        replaceId: "codegraph-live",
      });
      bindCodeGraphInteractions();
      bindTranscriptInteractions(elements.chatLog);
      setStatus(state.language === "en" ? "CodeGraph rescan complete" : "CodeGraph 重新掃描完成");
    }
  } catch (error) {
    renderCodeGraphError(error);
    showError(normalizeError(error, "CODEGRAPH_REBUILD_FAILED", t("errors.codeGraphFailed")));
    setStatus(t("errors.codeGraphFailed"));
  } finally {
    setCodeGraphButtonsBusy(false);
  }
}

function pinCodeGraphFiles() {
  const files = codeGraphMatchedFiles();
  if (!files.length) {
    renderCodeGraphStatusPanel(state.codeGraphStatus);
    return;
  }
  const rollback = new Set(state.pinnedFiles);
  files.forEach((path) => state.pinnedFiles.add(path));
  elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
  renderTree(state.tree, state.virtualTree.total || state.tree.length);
  schedulePinnedFilesSync(rollback);
  renderCodeGraphOperation(
    state.language === "en" ? "pinned" : "已釘選",
    t("statuses.codeGraphPinned", files.length),
    [...files.slice(0, 10), t("hints.codeGraphAskAiAfterPin")]
  );
  elements.codeGraphPinBtn.disabled = true;
  setStatus(t("statuses.codeGraphPinned", files.length));
}
