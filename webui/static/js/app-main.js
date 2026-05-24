document.querySelectorAll(".help-trigger").forEach((button) => {
  button.addEventListener("click", () => openHelp(button.dataset.help));
});

elements.langZhBtn.addEventListener("click", () => setLanguage("zh-Hant"));
elements.langEnBtn.addEventListener("click", () => setLanguage("en"));
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
elements.modelKey.addEventListener("change", () => {
  state.modelKey = elements.modelKey.value || state.modelKey;
  renderContextSelector();
  renderHardwareStatus();
  refreshModelStatus().catch(() => {});
});
elements.contextWindowSelect?.addEventListener("change", updateSelectedContext);
elements.contextCalibrateBtn?.addEventListener("click", calibrateSelectedModelContext);
elements.analyzeBtn.addEventListener("click", analyzeProject);
elements.refreshStatusBtn.addEventListener("click", refreshStatus);
elements.codeGraphUsePromptBtn?.addEventListener("click", () => queryCodeGraph());
elements.codeGraphRebuildBtn?.addEventListener("click", rebuildCodeGraphIndex);
elements.codeGraphPinBtn?.addEventListener("click", pinCodeGraphFiles);
elements.editPlanBtn?.addEventListener("click", generateEditPlan);
elements.gitDiffBtn?.addEventListener("click", () => showGitDiff());
elements.gitCheckpointBtn?.addEventListener("click", createGitCheckpoint);
let fileTreeSearchTimer = null;
  elements.fileTreeSearch?.addEventListener("input", () => {
  clearTimeout(fileTreeSearchTimer);
  fileTreeSearchTimer = window.setTimeout(() => {
    loadFileTree({ query: elements.fileTreeSearch.value || "" }).catch((error) => {
      showError(normalizeError(error, "FILE_TREE_FAILED", t("errors.fileTreeFailed")));
    });
  }, 180);
});
elements.attachImageBtn.addEventListener("click", () => elements.chatImageInput.click());
elements.chatImageInput.addEventListener("change", async (event) => {
  const files = [...(event.target.files || [])];
  for (const file of files) {
    await attachImageFile(file);
  }
});
elements.removeChatImageBtn.addEventListener("click", () => clearChatImage());
elements.newThreadBtn?.addEventListener("click", newThread);
elements.chatInput.addEventListener("paste", async (event) => {
  const items = [...(event.clipboardData?.items || [])];
  const imageItem = items.find((item) => item.type && item.type.startsWith("image/"));
  if (!imageItem) return;
  event.preventDefault();
  const file = imageItem.getAsFile();
  await attachImageFile(file);
});
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
bindChatAutoScroll();

window.CodeWorker = Object.assign(window.CodeWorker || {}, {
  state,
  elements,
  api: { requestJson },
  ui: { setStatus, setAiBusy, setUiState, renderProgress, renderContextCoverage, showError, clearError, startChatAutoScroll, maintainChatAutoScroll, appendLiveMessage, appendLiveText },
  tree: { renderTree, loadFileTree, renderVirtualTreeWindow },
  thread: { loadThreads, newThread, selectThread, renameThread, deleteThread },
  chat: { sendChat, streamChat, analyzeProject, renderProjectStructure, pinStructureRecommendedFiles, generateEditPlan, applyEditPlan, showGitDiff, createGitCheckpoint, restoreEditCheckpoint },
  codegraph: { queryCodeGraph, rebuildCodeGraphIndex, pinCodeGraphFiles, renderCodeGraphResults },
});

setUiState("idle");
applyTranslations();
refreshStatus()
  .then(() => setUiState(state.projectPath ? "ready" : "idle"))
  .catch(() => {
    setUiState("idle");
    setStatus(t("statuses.idle"));
  });
