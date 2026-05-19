function createTreeNode(path) {
  const node = elements.treeItemTemplate.content.firstElementChild.cloneNode(true);
  const checkbox = node.querySelector(".pin-checkbox");
  const button = node.querySelector(".tree-link");
  checkbox.checked = state.pinnedFiles.has(path);
  checkbox.disabled = state.uiState !== "ready";
  checkbox.addEventListener("change", () => {
    const rollback = new Set(state.pinnedFiles);
    if (checkbox.checked) state.pinnedFiles.add(path);
    else state.pinnedFiles.delete(path);
    elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
    schedulePinnedFilesSync(rollback);
  });
  button.textContent = path;
  button.disabled = state.uiState !== "ready";
  button.addEventListener("click", () => {
    if (button.disabled || checkbox.disabled) return;
    checkbox.checked = !checkbox.checked;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  });
  return node;
}

function renderVirtualTreeWindow() {
  if (!state.virtualTree.enabled) return;
  const items = state.virtualTree.items;
  const rowHeight = state.virtualTree.rowHeight;
  const scrollTop = elements.fileTree.scrollTop || 0;
  const height = elements.fileTree.clientHeight || 360;
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - state.virtualTree.buffer);
  const end = Math.min(items.length, Math.ceil((scrollTop + height) / rowHeight) + state.virtualTree.buffer);
  const windowNode = elements.fileTree.querySelector(".tree-virtual-window");
  if (!windowNode) return;
  windowNode.style.transform = `translateY(${start * rowHeight}px)`;
  windowNode.innerHTML = "";
  items.slice(start, end).forEach((path) => windowNode.appendChild(createTreeNode(path)));
}

function renderTree(tree, totalCount = null) {
  state.tree = (tree || []).map((entry) => typeof entry === "string" ? entry : entry.path).filter(Boolean);
  state.virtualTree.items = state.tree;
  state.virtualTree.total = Number.isFinite(Number(totalCount)) ? Number(totalCount) : state.tree.length;
  const visibleCount = state.tree.length;
  const count = state.virtualTree.total;
  if (elements.fileTreeCount) {
    elements.fileTreeCount.textContent = count === visibleCount ? String(visibleCount) : `${visibleCount}/${count}`;
  }
  elements.fileTree.innerHTML = "";
  elements.fileTree.classList.remove("is-virtual");
  if (!state.tree.length) {
    elements.fileTree.classList.add("empty");
    elements.fileTree.textContent = t("hints.initialTree");
    return;
  }
  elements.fileTree.classList.remove("empty");
  state.virtualTree.enabled = state.tree.length > 80;
  if (!state.virtualTree.enabled) {
    state.tree.forEach((path) => elements.fileTree.appendChild(createTreeNode(path)));
    return;
  }
  elements.fileTree.classList.add("is-virtual");
  const spacer = document.createElement("div");
  spacer.className = "tree-virtual-spacer";
  spacer.style.height = `${state.tree.length * state.virtualTree.rowHeight}px`;
  const windowNode = document.createElement("div");
  windowNode.className = "tree-virtual-window";
  spacer.appendChild(windowNode);
  elements.fileTree.appendChild(spacer);
  if (!state.virtualTree.bound) {
    elements.fileTree.addEventListener("scroll", renderVirtualTreeWindow);
    window.addEventListener("resize", renderVirtualTreeWindow);
    state.virtualTree.bound = true;
  }
  renderVirtualTreeWindow();
}

async function loadFileTree({ query = "", offset = 0, limit = 500 } = {}) {
  if (state.uiState !== "ready") return;
  const params = new URLSearchParams({ query, offset: String(offset), limit: String(limit) });
  const data = await requestJson(`/api/file-tree?${params.toString()}`);
  renderTree((data.items || []).map((item) => item.path), data.total);
}
