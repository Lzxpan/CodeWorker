const state = {
  uiState: "idle",
  projectPath: "",
  modelKey: "qwen35",
  modelCapabilities: {},
  language: localStorage.getItem("codeworker.language") || "zh-Hant",
  pinnedFiles: new Set(),
  pinSyncTimer: null,
  pinSyncRollback: null,
  pinSyncRequestId: 0,
  currentPreviewPath: null,
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
  chatImage: null,
};

const I18N = {
  "zh-Hant": {
    htmlLang: "zh-Hant",
    pageTitle: "CodeWorker V0.98b Web UI",
    brandTitle: "CodeWorker V0.98b",
    brandSubtitle: "本地離線專案分析與對話",
    languageSwitch: { zh: "繁中", en: "EN" },
    labels: {
      projectPath: "專案路徑",
      model: "模型",
      chatInput: "對話輸入",
      chatImage: "圖片附件",
    },
    headings: {
      errorPanel: "錯誤訊息",
      projectSummary: "專案摘要",
      fileTree: "檔案樹",
      chatPanel: "對話",
      previewPanel: "檔案預覽",
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
      attachImage: "上傳圖片",
      removeImage: "移除圖片",
    },
    hints: {
      firstRun: "第一次開啟專案時，若本機尚未有 runtime 或模型，系統會自動下載。",
      previewOnly: "僅供預覽，不會自動加入模型上下文",
      initialSummary: "尚未開啟專案。",
      initialTree: "尚未載入檔案。",
      initialPreviewPath: "未選擇檔案",
      initialPreview: "點左側檔案即可預覽內容。檔案預覽僅供閱讀，不會自動加入模型上下文。",
      projectOpened: "專案已開啟。",
      projectOpenedReady: "專案已開啟。你可以先按「分析專案」，或直接開始提問。",
      imagePasteHint: "可貼上截圖；送出時會使用目前選定且支援圖片的模型。",
      imageAttachedHint: "已附加圖片，可直接詢問圖片內容或搭配專案上下文提問。",
      contextCoverageHidden: "尚未送出上下文。",
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
      assistant: "Assistant",
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
      modelRedownloaded: "模型已重新下載",
      modelRedownloadFailed: "模型重新下載失敗",
      appliedPins: (count) => `已同步 ${count} 個釘選檔案`,
      uploadingImage: "正在上傳圖片",
      imageAttached: "圖片已附加",
      imageRemoved: "已移除圖片",
      imageModelUnsupported: "目前選定模型不支援圖片，請改用支援圖片的模型。",
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
      filePreviewFailed: "檔案預覽失敗。",
      pinFilesFailed: "更新上下文失敗。",
      chatFailed: "對話失敗。",
      resetHistoryFailed: "清空對話失敗。",
      modelReady: "模型已重新下載完成。",
      modelReadyDetails: "請再次按「開啟專案」重新啟動模型與索引流程。",
      taskFailed: "Task failed.",
      imageUploadFailed: "圖片上傳失敗。",
      emptyChat: "請輸入問題或附加圖片。",
      modelEmptyReply: "模型沒有產生可顯示的最終答案。",
      imageModelUnsupported: "目前選定模型不支援圖片輸入，請切換到支援圖片的模型後再送出。",
    },
  },
  en: {
    htmlLang: "en",
    pageTitle: "CodeWorker V0.98b Web UI",
    brandTitle: "CodeWorker V0.98b",
    brandSubtitle: "Local offline project analysis and chat",
    languageSwitch: { zh: "繁中", en: "EN" },
    labels: {
      projectPath: "Project path",
      model: "Model",
      chatInput: "Chat input",
      chatImage: "Image attachment",
    },
    headings: {
      errorPanel: "Errors",
      projectSummary: "Project summary",
      fileTree: "File tree",
      chatPanel: "Chat",
      previewPanel: "File preview",
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
      attachImage: "Attach image",
      removeImage: "Remove image",
    },
    hints: {
      firstRun: "On the first run, CodeWorker will automatically download missing runtime files or models.",
      previewOnly: "Preview only. This file is not automatically added to model context.",
      initialSummary: "No project opened yet.",
      initialTree: "No files loaded yet.",
      initialPreviewPath: "No file selected",
      initialPreview: "Click a file on the left to preview it. File preview is read-only and does not automatically join model context.",
      projectOpened: "Project opened.",
      projectOpenedReady: "Project opened. You can analyze it first or start asking questions right away.",
      imagePasteHint: "Paste a screenshot here. The request will use the currently selected model only if it supports images.",
      imageAttachedHint: "An image is attached. You can ask about the image alone or together with project context.",
      contextCoverageHidden: "No model context sent yet.",
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
      assistant: "Assistant",
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
      modelRedownloaded: "Model redownloaded",
      modelRedownloadFailed: "Model redownload failed",
      appliedPins: (count) => `Synced ${count} pinned files`,
      uploadingImage: "Uploading image",
      imageAttached: "Image attached",
      imageRemoved: "Image removed",
      imageModelUnsupported: "The selected model does not support image input. Switch to a vision-capable model.",
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
      filePreviewFailed: "File preview failed.",
      pinFilesFailed: "Failed to update model context.",
      chatFailed: "Chat failed.",
      resetHistoryFailed: "Failed to clear chat.",
      modelReady: "Model redownload completed.",
      modelReadyDetails: "Click Open project again to restart the model and project indexing flow.",
      taskFailed: "Task failed.",
      imageUploadFailed: "Image upload failed.",
      emptyChat: "Enter a question or attach an image.",
      modelEmptyReply: "The model did not return a displayable final answer.",
      imageModelUnsupported: "The selected model does not support image input. Switch to a vision-capable model and try again.",
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
      description: "選擇本次要用的本地模型。預設與主力模型是 Qwen 3.5；Gemma 4 E4B 保留為第二模型。一般對話與分析會直接顯示較接近模型原始輸出的內容。",
      usage: [
        "一般建議直接使用 Qwen 3.5 9B Vision。",
        "Qwen 3.5 同時支援文字與圖片，也作為目前主要的 code 分析模型。",
        "Gemma 4 E4B 目前保留為文字分析模型；本機 llama.cpp GGUF 路線尚未把圖片輸入列為正式支援。",
        "若要比較 Gemma 4 E4B 的分析與回答風格，可切換到 Gemma 4 E4B。",
        "切換模型後需重新開啟專案，系統才會改用新模型。",
      ],
      notes: [
        "較大的本地模型建議以 32GB RAM 作為較穩妥的目標，但不會因此阻擋啟動。",
        "若使用內顯，共用記憶體可能會讓模型可用的系統 RAM 變少。",
      ],
    },
    en: {
      title: "Model",
      description: "Select the local model for this session. Qwen 3.5 is the primary default; Gemma 4 E4B remains the secondary option. General chat and analysis stay closer to the model's original output.",
      usage: [
        "Qwen 3.5 9B Vision is the recommended default.",
        "Qwen 3.5 handles both text and image input and is now the main code-analysis model.",
        "Gemma 4 E4B currently remains a text-analysis model in this local llama.cpp GGUF route; image input is not yet a supported default path.",
        "Switch to Gemma 4 E4B if you want to compare its raw analysis and response style.",
        "After changing the model, reopen the project so the new model is actually used.",
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
        "完成後，摘要、檔案樹、檔案預覽、分析與對話才會解鎖。",
      ],
    },
    en: {
      title: "Open project",
      description: "Load the current folder into CodeWorker. This is required before the rest of the features become available.",
      usage: [
        "On the first run, CodeWorker checks runtime files, models, and Git status.",
        "If the folder is not already a git repository, CodeWorker will initialize one and create a baseline snapshot.",
        "After completion, summary, file tree, preview, analysis, and chat become available.",
      ],
    },
  },
  "analyze-project": {
    "zh-Hant": {
      title: "分析專案",
      description: "請模型根據目前已同步的釘選檔案做總覽分析。結果會直接保留較接近模型原始輸出的內容，不再做額外格式修飾。",
      usage: [
        "先在檔案樹勾選要分析的檔案。",
        "分析結果會出現在中間對話區。",
      ],
    },
    en: {
      title: "Analyze project",
      description: "Ask the model to summarize the currently pinned files. The result is shown closer to the model's original output instead of being heavily reformatted.",
      usage: [
        "Check the files you want in the file tree first.",
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
        "點檔名可在右側「檔案預覽」查看內容。",
        "左邊勾選框可把檔案加入釘選清單。",
      ],
    },
    en: {
      title: "File tree",
      description: "Shows the scanned file list. This is the only place where you decide which files become model context.",
      usage: [
        "Click a filename to preview it on the right.",
        "Use the checkbox to add a file to the pinned context list.",
      ],
    },
  },
  "file-preview": {
    "zh-Hant": {
      title: "檔案預覽",
      description: "顯示你在檔案樹點到的單一檔案內容，讓你先快速閱讀與確認內容。",
      usage: [
        "它是閱讀區，不是編輯器，也不是模型上下文來源。",
        "若要讓模型真的讀取該檔案，只要在檔案樹勾選即可。",
      ],
    },
    en: {
      title: "File preview",
      description: "Shows the content of the single file you clicked in the file tree so you can read it quickly.",
      usage: [
        "This is a reading area, not an editor, and not a model-context source by itself.",
        "If you want the model to use this file, just check it in the file tree.",
      ],
    },
  },
  "chat-panel": {
    "zh-Hant": {
      title: "對話",
      description: "你和本地模型互動的主區域。分析結果與一般提問都會顯示在這裡。",
      usage: [
        "先開啟專案，再勾選至少一個釘選檔案後開始提問。",
        "模型只會根據目前已同步的釘選檔案回答，不會自動讀取你正在預覽的檔案。",
      ],
    },
    en: {
      title: "Chat",
      description: "The main interaction area between you and the local model. Analysis results and general questions appear here.",
      usage: [
        "Open a project first, then pin at least one file before asking questions.",
        "The model only answers from the currently synced pinned files, not from whatever file you happen to preview.",
      ],
    },
  },
  "chat-input": {
    "zh-Hant": {
      title: "對話輸入",
      description: "輸入你要問模型的內容。模型會根據目前已同步的釘選檔案回答。",
      usage: [
        "可直接問：『登入流程在哪些檔案？』",
        "也可下指令：『先不要改檔，先分析 bug 可能位置。』",
      ],
    },
    en: {
      title: "Chat input",
      description: "Type what you want to ask or request. The model answers from the currently pinned files.",
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
  errorPanelTitle: document.getElementById("errorPanelTitle"),
  refreshStatusBtn: document.getElementById("refreshStatusBtn"),
  projectSummaryTitle: document.getElementById("projectSummaryTitle"),
  projectSummary: document.getElementById("projectSummary"),
  fileTreeTitle: document.getElementById("fileTreeTitle"),
  fileTree: document.getElementById("fileTree"),
  previewPanelTitle: document.getElementById("previewPanelTitle"),
  previewPath: document.getElementById("previewPath"),
  previewNote: document.getElementById("previewNote"),
  filePreview: document.getElementById("filePreview"),
  chatPanelTitle: document.getElementById("chatPanelTitle"),
  chatLog: document.getElementById("chatLog"),
  contextCoverageBanner: document.getElementById("contextCoverageBanner"),
  chatForm: document.getElementById("chatForm"),
  chatInputLabel: document.getElementById("chatInputLabel"),
  chatInput: document.getElementById("chatInput"),
  chatImageLabel: document.getElementById("chatImageLabel"),
  attachImageBtn: document.getElementById("attachImageBtn"),
  chatImageInput: document.getElementById("chatImageInput"),
  chatImagePasteHint: document.getElementById("chatImagePasteHint"),
  chatImagePreview: document.getElementById("chatImagePreview"),
  removeChatImageBtn: document.getElementById("removeChatImageBtn"),
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
    FILE_PREVIEW_FAILED: {
      message: t("errors.filePreviewFailed"),
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
  const meta = [attachment.mimeType, attachment.sizeBytes ? formatBytes(attachment.sizeBytes) : ""].filter(Boolean).join(" | ");
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
  const image = state.chatImage;
  elements.chatImagePreview.innerHTML = "";
  elements.chatImagePreview.classList.toggle("hidden", !image);
  elements.removeChatImageBtn.classList.toggle("hidden", !image);
  if (!image) return;
  elements.chatImagePreview.innerHTML = renderAttachmentHtml(image);
}

function formatContextCoverage(coverage) {
  if (!coverage || typeof coverage !== "object") {
    return "";
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
    return parts.join("");
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
  return parts.join("");
}

function renderContextCoverage(coverage) {
  state.lastContextCoverage = coverage || null;
  const text = formatContextCoverage(state.lastContextCoverage);
  if (!text) {
    elements.contextCoverageBanner.textContent = t("hints.contextCoverageHidden");
    elements.contextCoverageBanner.dataset.mode = "full";
    elements.contextCoverageBanner.classList.add("hidden");
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
  const hasPendingEdit = !!state.pendingEdit;

  elements.openProjectBtn.disabled = opening;
  elements.modelKey.disabled = opening;
  elements.projectPath.disabled = opening;
  elements.analyzeBtn.disabled = !ready || busy;
  elements.sendChatBtn.disabled = !ready || busy;
  elements.chatInput.disabled = !ready || busy;
  elements.clearChatBtn.disabled = !ready;
  elements.attachImageBtn.disabled = !ready || busy;
  elements.removeChatImageBtn.disabled = !ready || busy;
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
  state.chatImage = null;
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
  return requestJson("/api/uploads/image", {
    method: "POST",
    body: JSON.stringify({ name, mimeType, data }),
  });
}

async function attachImageFile(file) {
  if (!file) return;
  const mimeType = String(file.type || "").toLowerCase();
  if (!mimeType.startsWith("image/")) {
    showError({ code: "IMAGE_UPLOAD_FAILED", message: t("errors.imageUploadFailed"), details: "Unsupported image format." });
    return;
  }
  const data = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed to read image."));
    reader.readAsDataURL(file);
  });
  try {
    const image = await uploadImageData({
      name: file.name || "image",
      mimeType,
      data,
    });
    state.chatImage = {
      ...image,
      previewUrl: typeof data === "string" ? data : "",
    };
    renderChatImagePreview();
    if (selectedModelSupportsImages()) {
      setStatus(t("statuses.imageAttached"));
    } else {
      setStatus(t("statuses.imageModelUnsupported"));
      showError({
        code: "IMAGE_MODEL_UNSUPPORTED",
        message: t("errors.imageModelUnsupported"),
        details: `${getModelLabel(elements.modelKey.value)} does not currently accept image input in this CodeWorker build.`,
      });
    }
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

function appendMessage(role, content, attachments = []) {
  const normalizedContent = String(content || "").trim();
  const safeAttachments = Array.isArray(attachments) ? attachments : [];
  if (!normalizedContent && safeAttachments.length === 0) {
    return;
  }
  const item = document.createElement("div");
  item.className = `chat-item ${role}`;
  const attachmentHtml = safeAttachments.length
    ? `<div class="chat-attachments">${safeAttachments.map((entry) => renderAttachmentHtml(entry)).join("")}</div>`
    : "";
  item.innerHTML = `
    <div class="chat-role">${role === "user" ? t("roles.user") : t("roles.assistant")}</div>
    <div class="chat-content">${escapeHtml(normalizedContent)}</div>
    ${attachmentHtml}
  `;
  elements.chatLog.appendChild(item);
  elements.chatLog.scrollTop = elements.chatLog.scrollHeight;
}

function renderHistory(history) {
  elements.chatLog.innerHTML = "";
  history.forEach((item) => appendMessage(item.role, item.content, item.attachments || []));
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
  renderContextCoverage(state.lastContextCoverage);
  elements.chatInputLabel.textContent = t("labels.chatInput");
  elements.chatImageLabel.textContent = t("labels.chatImage");
  elements.attachImageBtn.textContent = t("buttons.attachImage");
  elements.chatImagePasteHint.textContent = t("hints.imagePasteHint");
  elements.removeChatImageBtn.textContent = t("buttons.removeImage");
  elements.sendChatBtn.textContent = t("buttons.send");
  elements.clearChatBtn.textContent = t("buttons.clearChat");
  elements.previewPanelTitle.textContent = t("headings.previewPanel");
  elements.previewNote.textContent = t("hints.previewOnly");
  elements.helpTitle.textContent = state.openHelpKey ? (localizeHelpEntry(state.openHelpKey)?.title || t("headings.helpModal")) : t("headings.helpModal");
  elements.closeHelpBtn.textContent = t("buttons.dismiss");
  updateChatPlaceholder();
  elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
  renderTree(state.tree);
  renderHistory(state.history);
  renderChatImagePreview();
  if (!state.currentPreviewPath) {
    elements.previewPath.textContent = t("hints.initialPreviewPath");
    elements.filePreview.textContent = state.projectPath ? t("hints.projectOpenedReady") : t("hints.initialPreview");
  }
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
  state.tree = tree;
  elements.fileTree.innerHTML = "";
  if (!tree.length) {
    elements.fileTree.classList.add("empty");
    elements.fileTree.textContent = t("hints.initialTree");
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
      const rollback = new Set(state.pinnedFiles);
      if (checkbox.checked) state.pinnedFiles.add(path);
      else state.pinnedFiles.delete(path);
      elements.projectSummary.textContent = formatProjectSummary(state.summaryRaw, [...state.pinnedFiles]);
      schedulePinnedFilesSync(rollback);
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
  state.modelKey = data.modelKey || "qwen35";
  state.modelCapabilities = data.models || {};
  state.uiState = data.uiState || (data.projectPath ? "ready" : "idle");
  state.summaryRaw = data.summary || "";
  clearTimeout(state.pinSyncTimer);
  state.pinSyncTimer = null;
  state.pinSyncRollback = null;
  state.currentPreviewPath = data.currentPreviewPath || null;
  state.pendingEdit = data.pendingEdit || null;
  state.history = data.history || [];
  elements.projectPath.value = state.projectPath;
  elements.modelKey.value = state.modelKey;
  elements.previewPath.textContent = state.currentPreviewPath || t("hints.initialPreviewPath");
  renderTree(data.tree || []);
  setPinnedFiles(data.pinnedFiles || []);
  renderHistory(state.history);
  renderPendingEdit(state.pendingEdit);
  renderContextCoverage(null);
  if (state.uiState !== "opening" && state.currentTaskKind !== "redownload-model") {
    setUiState(state.uiState);
    if (data.projectPath) {
      setStatus(t("statuses.ready"));
      elements.filePreview.textContent = elements.filePreview.textContent || t("hints.projectOpened");
    } else {
      setStatus(t("statuses.idle"));
    }
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
  state.currentPreviewPath = null;
  state.lastContextCoverage = null;
  elements.previewPath.textContent = t("hints.initialPreviewPath");
  elements.filePreview.textContent = t("hints.initialPreview");
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
  const modelKey = state.lastError?.modelKey || elements.modelKey.value || "qwen35";
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
  if (!requirePinnedFiles()) {
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
    appendMessage("assistant", data.reply);
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

async function loadFilePreview(path) {
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  elements.previewPath.textContent = path;
  elements.filePreview.textContent = state.language === "en" ? "Loading..." : "讀取中...";
  try {
    const data = await requestJson(`/api/file?path=${encodeURIComponent(path)}`);
    state.currentPreviewPath = data.path || path;
    elements.previewPath.textContent = state.currentPreviewPath;
    elements.filePreview.textContent = data.content;
  } catch (error) {
    elements.filePreview.textContent = "";
    showError(normalizeError(error, "FILE_PREVIEW_FAILED", t("errors.filePreviewFailed")));
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
  const image = state.chatImage;
  if (!message && !image) {
    showError({ code: "CHAT_FAILED", message: t("errors.emptyChat"), details: "" });
    return;
  }
  if (state.uiState !== "ready") {
    showError({ code: "PROJECT_NOT_READY", message: t("errors.projectNotReady"), details: "" });
    return;
  }
  if (!requirePinnedFiles({ allowWithoutPins: !!image })) {
    return;
  }
  if (image && !selectedModelSupportsImages()) {
    const modelKey = elements.modelKey.value || state.modelKey;
    showError({
      code: "IMAGE_MODEL_UNSUPPORTED",
      message: t("errors.imageModelUnsupported"),
      details: `${getModelLabel(modelKey)} does not currently accept image input in this CodeWorker build.`,
    });
    setStatus(t("statuses.chatFailed"));
    return;
  }
  clearError();
  appendMessage("user", message || t("hints.imageAttachedHint"), image ? [image] : []);
  elements.chatInput.value = "";
  setStatus(t("statuses.thinking"), true);
  try {
    const data = await requestJson("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        modelKey: elements.modelKey.value,
        imageId: image?.id || "",
      }),
    });
    if (data.plan) {
      renderPendingEdit(data.plan);
    }
    if (data.modelKey) {
      state.modelKey = data.modelKey;
      elements.modelKey.value = data.modelKey;
    }
    renderContextCoverage(data.contextCoverage || null);
    const reply = String(data.reply || "").trim();
    if (!reply) {
      throw { code: "MODEL_EMPTY_REPLY", message: t("errors.modelEmptyReply"), details: "" };
    }
    appendMessage("assistant", reply);
    clearChatImage({ silent: true });
    setStatus(t("statuses.done"));
  } catch (error) {
    setStatus(t("statuses.chatFailed"));
    const normalized = normalizeError(error, "CHAT_FAILED", t("errors.chatFailed"));
    showError(normalized);
    renderContextCoverage(null);
    appendMessage("assistant", `${state.language === "en" ? "Error:" : "發生錯誤："} ${localizeError(normalized).message}`);
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
elements.analyzeBtn.addEventListener("click", analyzeProject);
elements.refreshStatusBtn.addEventListener("click", refreshStatus);
elements.attachImageBtn.addEventListener("click", () => elements.chatImageInput.click());
elements.chatImageInput.addEventListener("change", async (event) => {
  const [file] = event.target.files || [];
  await attachImageFile(file);
});
elements.removeChatImageBtn.addEventListener("click", () => clearChatImage());
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
