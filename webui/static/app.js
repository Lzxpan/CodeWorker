const state = {
  uiState: "idle",
  projectPath: "",
  modelKey: "gemma4",
  modelCapabilities: {},
  modelContextByKey: { gemma4: 262144, qwen35: 262144 },
  contextOptions: [
    { label: "4k", value: 4096 },
    { label: "8k", value: 8192 },
    { label: "16k", value: 16384 },
    { label: "32k", value: 32768 },
    { label: "64k", value: 65536 },
    { label: "128k", value: 131072 },
    { label: "256k", value: 262144 },
  ],
  threads: [],
  activeThreadId: "",
  language: localStorage.getItem("codeworker.language") || "zh-Hant",
  pinnedFiles: new Set(),
  pinSyncTimer: null,
  pinSyncRollback: null,
  pinSyncRequestId: 0,
  pendingEdit: null,
  history: [],
  currentTaskId: null,
  currentTaskKind: null,
  lastError: null,
  lastStatusText: "待命",
  lastStatusBusy: false,
  lastProgress: { progress: 0, step: "", title: "背景作業執行中" },
  lastContextCoverage: null,
  summaryRaw: "",
  tree: [],
  openHelpKey: null,
  chatAttachments: [],
};

const I18N = {
  "zh-Hant": {
    htmlLang: "zh-Hant",
    pageTitle: "CodeWorker V1.01.000 Web UI",
    brandTitle: "CodeWorker V1.01.000",
    brandSubtitle: "本地離線專案分析與對話",
    languageSwitch: { zh: "繁中", en: "EN" },
    labels: {
      projectPath: "專案路徑",
      model: "模型",
      chatInput: "對話輸入",
      chatImage: "檔案附件",
      contextWindow: "Context",
      modelStatus: "模型狀態",
    },
    headings: {
      errorPanel: "錯誤訊息",
      projectSummary: "專案摘要",
      fileTree: "檔案樹",
      chatPanel: "對話",
      threadPanel: "對話串",
      helpModal: "功能說明",
    },
    buttons: {
      openProject: "開啟專案",
      analyzeProject: "分析專案",
      redownloadModel: "重新下載模型",
      dismiss: "關閉",
      refresh: "重新整理",
      send: "送出",
      clearChat: "清空對話",
      attachImage: "上傳檔案",
      removeImage: "移除附件",
      newThread: "新增",
      renameThread: "重新命名",
      deleteThread: "刪除",
    },
    hints: {
      firstRun: "第一次開啟專案時，若本機尚未有 runtime 或模型，系統會自動下載。",
      initialSummary: "尚未開啟專案。",
      initialTree: "尚未載入檔案。",
      projectOpened: "專案已開啟。",
      projectOpenedReady: "專案已開啟。你可以直接按「分析專案」建立/使用全專案快取，或勾選檔案後進行精準上下文對話。",
      imagePasteHint: "可貼上截圖，或上傳程式碼、設定、文件、圖片、音訊、影片等檔案。",
      imageAttachedHint: "已附加檔案，可直接詢問附件內容或搭配專案上下文提問。",
      contextCoverageHidden: "未使用專案上下文。",
    },
    placeholders: {
      projectPath: "點擊這裡選擇專案資料夾",
      chatDefault: "輸入你的問題或修改需求，例如：請分析登入流程涉及哪些檔案？",
    },
    helpSections: {
      usage: "使用方式",
      notes: "補充說明",
    },
    roles: {
      user: "你",
      assistant: "模型",
    },
    summary: {
      path: "專案路徑",
      fileCount: "檔案數量(已掃描)",
      totalBytes: "估計文字檔總大小",
      languages: "主要語言",
      entrypoints: "可能入口檔案",
      tests: "測試相關檔案",
      none: "無",
      notFound: "未明確找到",
      pinned: "已同步釘選檔案",
      noPins: "(無)",
      moreCount: (count) => `+${count} 個`,
    },
    statuses: {
      idle: "待命",
      ready: "專案已就緒",
      opening: "正在開啟專案",
      redownloading: "正在重新下載模型",
      thinking: "正在思考",
      done: "完成",
      chatFailed: "對話失敗",
      analyzing: "正在分析",
      analyzeDone: "分析完成",
      analyzeFailed: "分析失敗",
      openingFolder: "開啟資料夾選取視窗",
      pickFolderFailed: "選擇資料夾失敗",
      openFailed: "開啟失敗",
      updateContext: "更新上下文",
      updateFailed: "更新失敗",
      historyCleared: "對話已清空",
      contextUpdated: "Context 已更新",
      threadCreated: "對話串已建立",
      threadSelected: "已切換對話串",
      threadUpdated: "對話串已更新",
      threadDeleted: "對話串已刪除",
      generatingFile: "正在建立檔案預覽",
      fileGenerated: "檔案已建立預覽",
      modelRedownloaded: "模型已重新下載",
      modelRedownloadFailed: "模型重新下載失敗",
      appliedPins: (count) => `已同步 ${count} 個釘選檔案`,
      uploadingImage: "正在上傳檔案",
      imageAttached: "檔案已附加",
      imageRemoved: "已移除附件",
      imageModelUnsupported: "目前模型若無法處理圖片，會改用文字附件說明。",
    },
    progress: {
      defaultTitle: "背景作業執行中",
      waiting: "等待中",
      openTitle: "正在開啟專案",
      redownloadTitle: "正在重新下載模型",
    },
    errors: {
      unexpected: "發生未預期錯誤。",
      requestFailed: "Request failed.",
      pinnedRequiredMessage: "請先勾選釘選檔案。",
      pinnedRequiredDetails: "請先在檔案樹勾選至少一個檔案，模型才會根據這些檔案分析。",
      projectNotReady: "請先完成開啟專案。",
      projectPathInvalid: "請先選擇專案資料夾。",
      pickFolderFailed: "選擇資料夾失敗。",
      openProjectFailed: "開啟專案失敗。",
      modelDownloadFailed: "模型重新下載失敗。",
      analyzeFailed: "分析失敗。",
      fileTreeFailed: "檔案樹讀取失敗。",
      pinFilesFailed: "更新上下文失敗。",
      chatFailed: "對話失敗。",
      resetHistoryFailed: "清空對話失敗。",
      modelReady: "模型已重新下載完成。",
      modelReadyDetails: "請再次按「開啟專案」重新啟動模型與索引流程。",
      taskFailed: "Task failed.",
      imageUploadFailed: "檔案上傳失敗。",
      contextUpdateFailed: "Context 更新失敗。",
      threadFailed: "對話串操作失敗。",
      fileGenerationFailed: "檔案生成失敗。",
      emptyChat: "請輸入問題或附加檔案。",
      modelEmptyReply: "模型沒有產生可顯示的最終答案。",
      imageModelUnsupported: "目前模型若無法處理圖片，CodeWorker 會改用文字附件說明讓模型回覆限制。",
    },
  },
  en: {
    htmlLang: "en",
    pageTitle: "CodeWorker V1.01.000 Web UI",
    brandTitle: "CodeWorker V1.01.000",
    brandSubtitle: "Local offline project analysis and chat",
    languageSwitch: { zh: "繁中", en: "EN" },
    labels: {
      projectPath: "Project path",
      model: "Model",
      chatInput: "Chat input",
      chatImage: "File attachment",
      contextWindow: "Context",
      modelStatus: "Model status",
    },
    headings: {
      errorPanel: "Errors",
      projectSummary: "Project summary",
      fileTree: "File tree",
      chatPanel: "Chat",
      threadPanel: "Threads",
      helpModal: "Help",
    },
    buttons: {
      openProject: "Open project",
      analyzeProject: "Analyze project",
      redownloadModel: "Redownload model",
      dismiss: "Close",
      refresh: "Refresh",
      send: "Send",
      clearChat: "Clear chat",
      attachImage: "Attach file",
      removeImage: "Remove attachments",
      newThread: "New",
      renameThread: "Rename",
      deleteThread: "Delete",
    },
    hints: {
      firstRun: "On the first run, CodeWorker will automatically download missing runtime files or models.",
      initialSummary: "No project opened yet.",
      initialTree: "No files loaded yet.",
      projectOpened: "Project opened.",
      projectOpenedReady: "Project opened. You can analyze the full folder with the local cache, or pin files for focused context.",
      imagePasteHint: "Paste a screenshot, or attach code, config, documents, images, audio, or video.",
      imageAttachedHint: "A file is attached. You can ask about the attachment alone or together with project context.",
      contextCoverageHidden: "No project context used.",
    },
    placeholders: {
      projectPath: "Click here to choose a project folder",
      chatDefault: "Enter your question or change request, for example: Which files are involved in the login flow?",
    },
    helpSections: {
      usage: "How to use",
      notes: "Notes",
    },
    roles: {
      user: "You",
      assistant: "Model",
    },
    summary: {
      path: "Project path",
      fileCount: "Scanned files",
      totalBytes: "Estimated text size",
      languages: "Primary languages",
      entrypoints: "Possible entry points",
      tests: "Test-related files",
      none: "None",
      notFound: "Not clearly found",
      pinned: "Synced pinned files",
      noPins: "(none)",
      moreCount: (count) => `+${count} more`,
    },
    statuses: {
      idle: "Idle",
      ready: "Project ready",
      opening: "Opening project",
      redownloading: "Redownloading model",
      thinking: "Thinking",
      done: "Done",
      chatFailed: "Chat failed",
      analyzing: "Analyzing",
      analyzeDone: "Analysis complete",
      analyzeFailed: "Analysis failed",
      openingFolder: "Opening folder picker",
      pickFolderFailed: "Folder selection failed",
      openFailed: "Open failed",
      updateContext: "Updating context",
      updateFailed: "Context update failed",
      historyCleared: "Chat cleared",
      contextUpdated: "Context updated",
      threadCreated: "Thread created",
      threadSelected: "Thread selected",
      threadUpdated: "Thread updated",
      threadDeleted: "Thread deleted",
      generatingFile: "Creating file preview",
      fileGenerated: "File preview ready",
      modelRedownloaded: "Model redownloaded",
      modelRedownloadFailed: "Model redownload failed",
      appliedPins: (count) => `Synced ${count} pinned files`,
      uploadingImage: "Uploading file",
      imageAttached: "File attached",
      imageRemoved: "Attachments removed",
      imageModelUnsupported: "If the selected model cannot process images, CodeWorker sends a text attachment note instead.",
    },
    progress: {
      defaultTitle: "Background task running",
      waiting: "Waiting",
      openTitle: "Opening project",
      redownloadTitle: "Redownloading model",
    },
    errors: {
      unexpected: "An unexpected error occurred.",
      requestFailed: "Request failed.",
      pinnedRequiredMessage: "Please pin at least one file first.",
      pinnedRequiredDetails: "Please check at least one file in the file tree before asking the model to analyze or answer.",
      projectNotReady: "Please finish opening the project first.",
      projectPathInvalid: "Please choose a project folder first.",
      pickFolderFailed: "Failed to choose a folder.",
      openProjectFailed: "Failed to open project.",
      modelDownloadFailed: "Failed to redownload model.",
      analyzeFailed: "Analysis failed.",
      fileTreeFailed: "Failed to load file tree.",
      pinFilesFailed: "Failed to update model context.",
      chatFailed: "Chat failed.",
      resetHistoryFailed: "Failed to clear chat.",
      modelReady: "Model redownload completed.",
      modelReadyDetails: "Click Open project again to restart the model and project indexing flow.",
      taskFailed: "Task failed.",
      imageUploadFailed: "File upload failed.",
      contextUpdateFailed: "Context update failed.",
      threadFailed: "Thread operation failed.",
      fileGenerationFailed: "File generation failed.",
      emptyChat: "Enter a question or attach a file.",
      modelEmptyReply: "The model did not return a displayable final answer.",
      imageModelUnsupported: "If the selected model cannot process images, CodeWorker sends a text attachment note so the model can explain the limitation.",
    },
  },
};

const HELP_CONTENT = {
  "project-path": {
    "zh-Hant": {
      title: "專案路徑",
      description: "這裡填要分析的專案資料夾。開啟專案時，CodeWorker 會以這個資料夾為根目錄建立 git 基線、掃描檔案並準備上下文。",
      usage: [
        "直接點一下路徑框，就會開啟 Windows 原生資料夾選取視窗。",
        "選完後，路徑會自動填回輸入框。",
        "建議選真正的程式碼專案根目錄，不要選整個下載資料夾或大量影音資源資料夾。",
      ],
    },
    en: {
      title: "Project path",
      description: "Choose the project folder you want to analyze. When you open a project, CodeWorker uses this folder as the root for git baseline setup, file scanning, and context preparation.",
      usage: [
        "Click the path field to open the native Windows folder picker.",
        "After you choose a folder, the path is filled back into the input automatically.",
        "Pick the real project root, not a generic download folder or a directory full of media assets.",
      ],
    },
  },
  "model-key": {
    "zh-Hant": {
      title: "模型",
      description: "選擇本次要用的本地模型。預設與主力模型是 Gemma 4 26B；它由 CodeWorker 內建 llama.cpp service 啟動，不依賴 Ollama。",
      usage: [
        "一般建議直接使用 Gemma 4 26B。",
        "Gemma 4 26B 支援文字與圖片，影片會由 CodeWorker 先抽 keyframes 再交給模型分析。",
        "Qwen 3.5 9B Vision 仍保留為可選備用模型。",
        "所有模型都會先嘗試目前功能；若模型或後端做不到，會以回覆說明限制。",
        "一般聊天可直接使用；開啟專案後才會加入 pinned files 或 RAG 上下文。",
      ],
      notes: [
        "較大的本地模型建議以 32GB RAM 作為較穩妥的目標，但不會因此阻擋啟動。",
        "若使用內顯，共用記憶體可能會讓模型可用的系統 RAM 變少。",
      ],
    },
    en: {
      title: "Model",
      description: "Select the local model for this session. Gemma 4 26B is the primary default and is served by CodeWorker's bundled llama.cpp service without Ollama.",
      usage: [
        "Gemma 4 26B is the recommended default.",
        "Gemma 4 26B handles text and image input; videos are converted to keyframes before analysis.",
        "Qwen 3.5 9B Vision remains available as a backup model.",
        "Every feature is attempted with the selected model first; if the model or backend cannot do it, the reply should explain the limitation.",
        "General chat works immediately; project context is added after opening a project and using pinned files or RAG.",
      ],
      notes: [
        "For larger local models, 32GB RAM is the more reliable target, but CodeWorker does not hard-block startup on that basis.",
        "Integrated graphics may reduce the amount of system memory actually available to the model.",
      ],
    },
  },
  "progress-panel": {
    "zh-Hant": {
      title: "進度條",
      description: "顯示目前背景任務進行到哪個步驟。開專案時會依序經過路徑檢查、Git 準備、模型啟動、專案索引。",
      usage: [
        "百分比是目前任務進度。",
        "下面的文字會顯示當前步驟與補充訊息。",
        "若長時間停在同一步，通常代表該步驟真的在進行較重的工作。",
      ],
    },
    en: {
      title: "Progress bar",
      description: "Shows which background step is currently running. Opening a project usually goes through path validation, Git preparation, model startup, and project indexing.",
      usage: [
        "The percentage shows task progress.",
        "The line below shows the current step and extra detail.",
        "If it stays on one step for a long time, that step is usually doing genuinely heavy work.",
      ],
    },
  },
  "open-project": {
    "zh-Hant": {
      title: "開啟專案",
      description: "把目前輸入的資料夾載入到 CodeWorker。這是使用其他功能前的必要步驟。",
      usage: [
        "第一次開專案時，系統會檢查 runtime、模型與 git 狀態。",
        "若資料夾不是 git repo，系統會自動建立 `.git` 與基線快照。",
        "完成後，摘要、檔案樹、分析與對話才會解鎖。",
      ],
    },
    en: {
      title: "Open project",
      description: "Load the current folder into CodeWorker. This is required before the rest of the features become available.",
      usage: [
        "On the first run, CodeWorker checks runtime files, models, and Git status.",
        "If the folder is not already a git repository, CodeWorker will initialize one and create a baseline snapshot.",
        "After completion, summary, file tree, analysis, and chat become available.",
      ],
    },
  },
  "analyze-project": {
    "zh-Hant": {
      title: "分析專案",
      description: "請模型做專案總覽分析。未勾選檔案時會建立/使用全專案快取；有勾選檔案時則優先使用 pinned files 做精準上下文。",
      usage: [
        "可直接按「分析專案」建立本機快取並分析整個資料夾。",
        "若只想分析特定檔案，先在檔案樹勾選它們。",
        "分析結果會出現在中間對話區。",
      ],
    },
    en: {
      title: "Analyze project",
      description: "Ask the model for a project overview. Without pinned files, CodeWorker builds or reuses the full-project cache; with pinned files, it uses focused pinned context.",
      usage: [
        "Click Analyze project directly to build the local cache and analyze the folder.",
        "Pin files first only when you want a focused file-level analysis.",
        "The analysis result appears in the main chat panel.",
      ],
    },
  },
  "error-panel": {
    "zh-Hant": {
      title: "錯誤訊息",
      description: "當下載、模型啟動、專案開啟或對話發生問題時，這裡會顯示錯誤碼、摘要與詳細內容。",
      usage: [
        "先看錯誤碼與摘要，再看詳細內容。",
        "若有 log 路徑，可用來進一步除錯。",
      ],
    },
    en: {
      title: "Error panel",
      description: "When downloads, model startup, project loading, or chat fail, this panel shows the error code, summary, and details.",
      usage: [
        "Read the error code and summary first, then inspect the detailed message.",
        "If a log path is shown, use it for deeper troubleshooting.",
      ],
    },
  },
  "redownload-model": {
    "zh-Hant": {
      title: "重新下載模型",
      description: "當模型檔損壞、下載不完整或讀取失敗時，用這個功能重新抓指定模型。",
      usage: [
        "按下後會在背景重新下載模型。",
        "下載完成後，再按一次「開啟專案」。",
      ],
    },
    en: {
      title: "Redownload model",
      description: "Use this when a model file is corrupted, incomplete, or cannot be read.",
      usage: [
        "The selected model is downloaded again in the background.",
        "After the download finishes, click Open project again.",
      ],
    },
  },
  "dismiss-error": {
    "zh-Hant": {
      title: "關閉錯誤",
      description: "先把目前的錯誤卡收起來，不會刪除任何資料或修正問題。",
      usage: ["只會隱藏錯誤顯示。"],
    },
    en: {
      title: "Close error",
      description: "Hide the current error card. This does not fix the issue or remove any data.",
      usage: ["This only hides the error display."],
    },
  },
  "project-summary": {
    "zh-Hant": {
      title: "專案摘要",
      description: "用來快速看整個專案的大方向。它不是原始碼本身，而是系統掃描後整理出的重點資訊。",
      usage: [
        "可看到專案路徑、已掃描檔案數量、估計文字檔大小、主要語言、可能入口檔案與測試位置。",
        "也會顯示目前已同步的釘選檔案清單，方便確認模型此刻會看哪些檔案。",
      ],
    },
    en: {
      title: "Project summary",
      description: "A quick project overview generated from the scanned workspace. It is not raw source code; it is a summary of key facts.",
      usage: [
        "You can see project path, scanned file count, estimated text size, major languages, likely entry points, and test locations.",
        "It also shows the pinned files currently used as model context.",
      ],
    },
  },
  "refresh-status": {
    "zh-Hant": {
      title: "重新整理",
      description: "重新抓一次目前載入中的專案狀態與畫面內容。",
      usage: ["適合在專案已開啟後，重新同步摘要、檔案樹與對話歷史。"],
    },
    en: {
      title: "Refresh",
      description: "Fetch the current project state and refresh the visible workspace data.",
      usage: ["Useful after the project is already opened and you want to sync summary, file tree, and chat history again."],
    },
  },
  "file-tree": {
    "zh-Hant": {
      title: "檔案樹",
      description: "顯示目前已掃描到的檔案清單。這裡是你選擇模型上下文檔案的唯一入口。",
      usage: [
        "點檔名或左邊勾選框可把檔案加入釘選清單。",
        "未釘選檔案時，一般聊天會使用全專案搜尋快取找相關片段。",
      ],
    },
    en: {
      title: "File tree",
      description: "Shows the scanned file list. This is the only place where you decide which files become model context.",
      usage: [
        "Click a filename or checkbox to add it to the pinned context list.",
        "When no files are pinned, normal chat uses the full-project search cache to find related snippets.",
      ],
    },
  },
  "chat-panel": {
    "zh-Hant": {
      title: "對話",
      description: "你和本地模型互動的主區域。一般問答、專案分析與 streaming 思考/回答都會顯示在這裡。",
      usage: [
        "沒有開啟專案也可以直接提問，系統會當成一般問答。",
        "開啟專案並釘選檔案後，模型才會收到對應的專案上下文。",
      ],
    },
    en: {
      title: "Chat",
      description: "The main interaction area between you and the local model. General Q&A, project analysis, and streaming reasoning/content appear here.",
      usage: [
        "You can ask general questions before opening a project.",
        "After opening a project and pinning files, the model receives the matching project context.",
      ],
    },
  },
  "chat-input": {
    "zh-Hant": {
      title: "對話輸入",
      description: "輸入你要問模型的內容。未開啟專案時是一般問答；有專案上下文時會一起送出。",
      usage: [
        "可直接問：『登入流程在哪些檔案？』",
        "也可下指令：『先不要改檔，先分析 bug 可能位置。』",
      ],
    },
    en: {
      title: "Chat input",
      description: "Type what you want to ask or request. Before a project is opened this is normal Q&A; project context is added when available.",
      usage: [
        "Ask direct questions such as: Which files are involved in the login flow?",
        "You can also give instructions such as: Do not change files yet, analyze where the bug might be first.",
      ],
    },
  },
  "send-chat": {
    "zh-Hant": {
      title: "送出",
      description: "把目前輸入框的問題送到模型。",
      usage: [
        "送出前請確認已開啟專案。",
        "回答會直接保留較接近模型原始輸出的內容，不再額外做大幅清洗或壓縮。",
      ],
    },
    en: {
      title: "Send",
      description: "Send the current input to the model.",
      usage: [
        "Make sure the project is opened before sending.",
        "Replies now stay closer to the model's original output instead of being heavily cleaned up.",
      ],
    },
  },
  "clear-chat": {
    "zh-Hant": {
      title: "清空對話",
      description: "清掉目前頁面上的對話歷史，讓你重新開始一輪提問。",
      usage: [
        "只清除這次 web UI 的對話內容。",
        "不會改變目前已同步的釘選檔案。",
      ],
    },
    en: {
      title: "Clear chat",
      description: "Clear the current chat history in this page so you can start over.",
      usage: [
        "This only clears the current Web UI conversation history.",
        "It does not change the currently applied pinned files.",
      ],
    },
  },
};

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
  modelStatus: document.getElementById("modelStatus"),
  errorPanelTitle: document.getElementById("errorPanelTitle"),
  refreshStatusBtn: document.getElementById("refreshStatusBtn"),
  projectSummaryTitle: document.getElementById("projectSummaryTitle"),
  projectSummary: document.getElementById("projectSummary"),
  fileTreeTitle: document.getElementById("fileTreeTitle"),
  fileTreeSearch: document.getElementById("fileTreeSearch"),
  fileTree: document.getElementById("fileTree"),
  chatPanelTitle: document.getElementById("chatPanelTitle"),
  chatLog: document.getElementById("chatLog"),
  contextCoverageBanner: document.getElementById("contextCoverageBanner"),
  agentPanel: document.getElementById("agentPanel"),
  pendingActionPanel: document.getElementById("pendingActionPanel"),
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
    .replaceAll(">", "&gt;");
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
    const rebuilt = Boolean(coverage.indexRebuilt);
    if (state.language === "en") {
      return `Full-project search context: ${rebuilt ? "rebuilt" : "reused"} local index, ${indexFiles} indexed file(s), sent ${filesSent}/${selectedFiles} matching summary/chunk item(s).${memorySuffix}`;
    }
    return `全專案搜尋上下文：${rebuilt ? "已重建" : "沿用"}本機索引，已索引 ${indexFiles} 個檔案，本次送出 ${filesSent}/${selectedFiles} 個命中摘要/片段。${memorySuffix}`;
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

function renderContextCoverage(coverage) {
  state.lastContextCoverage = coverage || null;
  const text = formatContextCoverage(state.lastContextCoverage);
  if (!text) {
    elements.contextCoverageBanner.textContent = t("hints.contextCoverageHidden");
    elements.contextCoverageBanner.dataset.mode = "full";
    elements.contextCoverageBanner.classList.remove("hidden");
    return;
  }
  elements.contextCoverageBanner.textContent = text;
  elements.contextCoverageBanner.dataset.mode = state.lastContextCoverage?.truncated ? "excerpt" : "full";
  elements.contextCoverageBanner.classList.remove("hidden");
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

function setUiState(nextState) {
  state.uiState = nextState;
  const ready = nextState === "ready";
  const opening = nextState === "opening";
  const busy = opening || state.currentTaskKind === "redownload-model";
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

function renderModelOptions(models = {}) {
  const selected = elements.modelKey.value || state.modelKey || "gemma4";
  const entries = Object.entries(models);
  if (!entries.length) return;
  entries.forEach(([key, model]) => {
    state.modelContextByKey[key] = Number(model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow || state.modelContextByKey[key] || 262144);
  });
  elements.modelKey.innerHTML = entries.map(([key, model]) => (
    `<option value="${escapeHtml(key)}">${escapeHtml(model.displayName || key)}</option>`
  )).join("");
  elements.modelKey.value = models[selected] ? selected : (state.modelKey || entries[0][0]);
  renderContextSelector();
}

function renderContextSelector(options = state.contextOptions) {
  if (!elements.contextWindowSelect) return;
  const selectedModel = elements.modelKey.value || state.modelKey || "gemma4";
  const selectedContext = Number(state.modelContextByKey[selectedModel] || 262144);
  const normalizedOptions = Array.isArray(options) && options.length ? options : state.contextOptions;
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
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
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
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
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
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function scrollLiveReasoningToBottom(live) {
  if (!live?.reasoningBody) return;
  if (live.reasoning?.open) {
    live.reasoningBody.scrollTop = live.reasoningBody.scrollHeight;
  }
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
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

function renderHistory(history) {
  elements.chatLog.innerHTML = "";
  history.forEach((item) => appendMessage(item.role, item.content, item.attachments || [], item));
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
  document.title = t("pageTitle");
  elements.brandTitle.textContent = t("brandTitle");
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
  elements.firstRunHint.textContent = t("hints.firstRun");
  elements.errorPanelTitle.textContent = t("headings.errorPanel");
  elements.errorActionBtn.textContent = t("buttons.redownloadModel");
  elements.dismissErrorBtn.textContent = t("buttons.dismiss");
  elements.projectSummaryTitle.textContent = t("headings.projectSummary");
  elements.refreshStatusBtn.textContent = t("buttons.refresh");
  elements.fileTreeTitle.textContent = t("headings.fileTree");
  elements.chatPanelTitle.textContent = t("headings.chatPanel");
  if (elements.threadPanelTitle) elements.threadPanelTitle.textContent = t("headings.threadPanel");
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
  renderHistory(state.history);
  renderThreads(state.threads);
  renderContextSelector();
  renderChatImagePreview();
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

function renderTree(tree) {
  state.tree = (tree || []).map((entry) => typeof entry === "string" ? entry : entry.path).filter(Boolean);
  elements.fileTree.innerHTML = "";
  if (!state.tree.length) {
    elements.fileTree.classList.add("empty");
    elements.fileTree.textContent = t("hints.initialTree");
    return;
  }
  elements.fileTree.classList.remove("empty");
  state.tree.forEach((path) => {
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
    elements.fileTree.appendChild(node);
  });
}

async function loadFileTree({ query = "", offset = 0, limit = 500 } = {}) {
  if (state.uiState !== "ready") return;
  const params = new URLSearchParams({ query, offset: String(offset), limit: String(limit) });
  const data = await requestJson(`/api/file-tree?${params.toString()}`);
  renderTree((data.items || []).map((item) => item.path));
}

async function refreshStatus() {
  const data = await requestJson("/api/status");
  state.projectPath = data.projectPath || "";
  state.modelKey = data.modelKey || "gemma4";
  state.modelCapabilities = data.models || {};
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
  elements.projectPath.value = state.projectPath;
  renderModelOptions(state.modelCapabilities);
  elements.modelKey.value = state.modelKey;
  renderContextSelector();
  renderTree(data.tree || []);
  setPinnedFiles(data.pinnedFiles || []);
  renderHistory(state.history);
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
  }
  refreshModelStatus().catch(() => {});
}

async function refreshModelStatus() {
  if (!elements.modelStatus) return;
  const data = await requestJson("/api/models");
  const modelKey = elements.modelKey.value || state.modelKey || data.defaultModelKey || "gemma4";
  const model = data.models?.[modelKey];
  if (!model) {
    elements.modelStatus.textContent = `${t("labels.modelStatus")}: ${modelKey}`;
    return;
  }
  const installed = model.installed ? (state.language === "en" ? "installed" : "已下載") : (state.language === "en" ? "not downloaded" : "未下載");
  const ready = model.ready ? (state.language === "en" ? "ready" : "服務中") : (state.language === "en" ? "stopped" : "未啟動");
  state.modelContextByKey[modelKey] = Number(model.selectedContextWindow || model.effectiveContextWindow || model.contextWindow || state.modelContextByKey[modelKey] || 262144);
  renderContextSelector(data.contextOptions || model.contextOptions || state.contextOptions);
  elements.modelStatus.textContent = `${t("labels.modelStatus")}: ${model.displayName || modelKey} · ${installed} · ${ready} · port ${model.port || "-"} · ctx ${model.selectedContextWindow || model.contextWindow || "-"}`;
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
    elements.chatLog.innerHTML = "";
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
      state.modelKey = data.status.modelKey || state.modelKey;
      elements.modelKey.value = state.modelKey;
      renderHistory(state.history);
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
      renderHistory(state.history);
      renderPendingEdit(data.status.pendingEdit || null);
    }
    setStatus(t("statuses.threadDeleted"));
  } catch (error) {
    showError(normalizeError(error, "THREAD_DELETE_FAILED", t("errors.threadFailed")));
  }
}

function renderGeneratedFileAction(action) {
  renderGeneratedFileActions(action ? [action] : []);
}

function renderGeneratedFileActions(actions) {
  if (!elements.pendingActionPanel) return;
  const safeActions = Array.isArray(actions) ? actions.filter(Boolean) : [];
  if (!safeActions.length) {
    elements.pendingActionPanel.classList.add("hidden");
    elements.pendingActionPanel.innerHTML = "";
    return;
  }
  elements.pendingActionPanel.classList.remove("hidden");
  const title = safeActions.length > 1
    ? (state.language === "en" ? "Generated file previews" : "生成檔案預覽")
    : (state.language === "en" ? "Generated file preview" : "生成檔案預覽");
  elements.pendingActionPanel.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    ${safeActions.map((action) => renderGeneratedFileActionCard(action)).join("")}
  `;
  safeActions.forEach((action) => {
    elements.pendingActionPanel.querySelector(`[data-action-id="${CSS.escape(String(action.id || ""))}"] [data-action="confirm-generated"]`)?.addEventListener("click", () => confirmGeneratedFile(action.id));
    elements.pendingActionPanel.querySelector(`[data-action-id="${CSS.escape(String(action.id || ""))}"] [data-action="cancel-generated"]`)?.addEventListener("click", () => cancelGeneratedFile(action.id));
  });
}

function renderGeneratedFileActionCard(action) {
  if (!action || !elements.pendingActionPanel) return;
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

function removeGeneratedActionCard(actionId) {
  const card = elements.pendingActionPanel?.querySelector(`[data-action-id="${CSS.escape(String(actionId || ""))}"]`);
  card?.remove();
  if (!elements.pendingActionPanel?.querySelector(".generated-action-card")) {
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
    renderProgress(task.progress || 0, buildProgressLabel(task), title);

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

async function analyzeProject() {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  clearError();
  setStatus(t("statuses.analyzing"), true);
  try {
    const data = await requestJson("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ modelKey: elements.modelKey.value }),
    });
    renderContextCoverage(data.contextCoverage || null);
    appendMessage("assistant", data.reply, [], data);
    setStatus(t("statuses.analyzeDone"));
  } catch (error) {
    setStatus(t("statuses.analyzeFailed"));
    showError(normalizeError(error, "ANALYZE_FAILED", t("errors.analyzeFailed")));
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
  if (!requirePinnedFiles()) {
    return;
  }
  clearError();
  appendMessage("user", message);
  elements.chatInput.value = "";
  setStatus(state.language === "en" ? "Generating edit suggestion" : "正在產生修改建議", true);
  try {
    const data = await requestJson("/api/edit/plan", {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderPendingEdit(data.plan);
    const modeLabel = data.plan.mode === "advisory" ? (state.language === "en" ? "advisory" : "文字模式") : (state.language === "en" ? "precise" : "精準模式");
    appendMessage("assistant", `${state.language === "en" ? "Edit suggestion generated" : "已產生修改建議"} (${modeLabel})\n\n${buildPendingEditText(data.plan)}`);
    setStatus(state.language === "en" ? "Edit suggestion ready" : "修改建議已產生");
    setUiState("ready");
  } catch (error) {
    setStatus(state.language === "en" ? "Edit suggestion failed" : "產生建議失敗");
    showError(normalizeError(error, "EDIT_PLAN_FAILED", state.language === "en" ? "Failed to generate edit suggestion." : "產生修改建議失敗。"));
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
  appendMessage("user", message || t("hints.imageAttachedHint"), attachments);
  const selectedModelKey = elements.modelKey.value || state.modelKey;
  const liveTarget = appendLiveMessage("assistant", "", [], { modelKey: selectedModelKey, modelName: getModelLabel(selectedModelKey) });
  elements.chatInput.value = "";
  setStatus(t("statuses.thinking"), true);
  let completed = false;
  try {
    await streamChat({
      message,
      modelKey: selectedModelKey,
      attachmentIds: attachments.map((entry) => entry.id).filter(Boolean),
    }, (eventName, data) => {
      if (eventName === "context") {
        renderContextCoverage(data.contextCoverage || null);
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
    setStatus(completed ? t("statuses.done") : t("statuses.chatFailed"));
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
      renderContextCoverage(null);
      clearChatImage({ silent: true });
      setStatus(state.uiState === "ready" ? t("statuses.ready") : t("statuses.historyCleared"));
    })
    .catch((error) => showError(normalizeError(error, "RESET_HISTORY_FAILED", t("errors.resetHistoryFailed"))));
}

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
  refreshModelStatus().catch(() => {});
});
elements.contextWindowSelect?.addEventListener("change", updateSelectedContext);
elements.analyzeBtn.addEventListener("click", analyzeProject);
elements.refreshStatusBtn.addEventListener("click", refreshStatus);
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

setUiState("idle");
applyTranslations();
refreshStatus()
  .then(() => setUiState(state.projectPath ? "ready" : "idle"))
  .catch(() => {
    setUiState("idle");
    setStatus(t("statuses.idle"));
  });
