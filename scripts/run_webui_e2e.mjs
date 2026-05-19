import { test, expect } from "@playwright/test";

const WEBUI_URL = process.env.CODEWORKER_WEBUI_URL || "http://127.0.0.1:8764";
const VIEWPORTS = [320, 641, 768, 1024, 1440];

function ok(data) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ ok: true, data }),
  };
}

async function installCodeGraphMocks(page) {
  const nodes = [
    {
      id: "node-form1",
      kind: "class",
      name: "Form1",
      qualifiedName: "Form1.cs::Form1",
      path: "Form1.cs",
      language: "C#",
      lineStart: 1,
      lineEnd: 80,
      signature: "public partial class Form1 : Form",
    },
    {
      id: "node-audio-manager",
      kind: "class",
      name: "AudioManager",
      qualifiedName: "AudioManager.cs::AudioManager",
      path: "AudioManager.cs",
      language: "C#",
      lineStart: 60,
      lineEnd: 120,
      signature: "internal sealed class AudioManager : IDisposable",
    },
  ];
  const edges = [
    {
      kind: "calls",
      line: 72,
      source: { name: "Form1", kind: "class", path: "Form1.cs", line: 1 },
      target: { name: "AudioManager", kind: "class", path: "AudioManager.cs", line: 60 },
    },
  ];
  const status = {
    ready: true,
    nodeCount: 14,
    edgeCount: 10,
    unresolvedCount: 3,
    files: 7,
    indexDir: "e2e",
    indexUpdatedAt: "2026-05-19 00:00:00",
    sampleSymbols: ["Form1", "AudioManager"],
    sampleFiles: ["Program.cs"],
  };

  await page.route("**/api/codegraph/status", async (route) => {
    await route.fulfill(ok(status));
  });
  await page.route("**/api/codegraph/query", async (route) => {
    const request = route.request();
    const body = request.postDataJSON?.() || {};
    const query = String(body.query || "renderTree");
    const hasMatch = /Form1|AudioManager|Program\.cs/i.test(query);
    await route.fulfill(ok({
      query,
      limit: body.limit || 8,
      nodes: hasMatch ? nodes : [],
      edges: hasMatch ? edges : [],
      matchedFiles: hasMatch ? ["Form1.cs", "AudioManager.cs"] : [],
      suggestions: ["Form1", "AudioManager", "Program.cs"],
      message: hasMatch
        ? `CodeGraph found matches for: ${query}`
        : `CodeGraph could not find '${query}' in the current project. Try a symbol, class, function, or file from the suggestions.`,
      status,
      context: hasMatch ? "CODE GRAPH CONTEXT\n- Form1 at Form1.cs:1" : "",
      coverage: { ready: true, nodeCount: 14, edgeCount: 10, nodesSent: hasMatch ? 2 : 0, edgesSent: hasMatch ? 1 : 0 },
      transcriptItem: {
        id: `e2e-codegraph-${query.replace(/\W+/g, "-")}`,
        kind: "tool-codegraph",
        role: "tool",
        title: "CodeGraph 查詢",
        content: hasMatch ? `CodeGraph found matches for: ${query}` : `CodeGraph could not find ${query}`,
        createdAt: Date.now() / 1000,
        data: { operation: "query", result: { query, nodes: hasMatch ? nodes : [], edges: hasMatch ? edges : [], matchedFiles: hasMatch ? ["Form1.cs", "AudioManager.cs"] : [], suggestions: ["Form1", "AudioManager", "Program.cs"], status } },
      },
    }));
  });
  await page.route("**/api/index/rebuild", async (route) => {
    await route.fulfill(ok({
      indexDir: "e2e",
      files: 7,
      chunks: 20,
      durationMs: 1200,
      indexUpdatedAt: "2026-05-19 00:00:01",
      sampleSymbols: ["Form1", "AudioManager"],
      sampleFiles: ["Program.cs"],
      codeGraph: { nodes: 14, edges: 10, unresolvedReferences: 3 },
      transcriptItem: {
        id: "e2e-rebuild",
        kind: "tool-codegraph",
        role: "tool",
        title: "重新掃描索引",
        content: "",
        createdAt: Date.now() / 1000,
        data: { operation: "rebuild", result: { indexDir: "e2e", files: 7, chunks: 20, durationMs: 1200, indexUpdatedAt: "2026-05-19 00:00:01", sampleSymbols: ["Form1", "AudioManager"], sampleFiles: ["Program.cs"], codeGraph: { nodes: 14, edges: 10, unresolvedReferences: 3 } } },
      },
    }));
  });
  await page.route("**/api/project/structure", async (route) => {
    const structure = {
      projectPath: "C:/e2e",
      categories: {
        entrypoints: ["Program.cs", "src/main.ts"],
        projectConfigs: ["Game.csproj", "package.json"],
        sourceFiles: ["Program.cs", "Game.cs", "webui/static/js/app-tree.js"],
        uiFiles: ["Form1.Designer.cs"],
        assetFiles: ["Assets/Sounds/a.wav"],
        testFiles: ["tests/test_app.py"],
        generatedFiles: ["obj/Debug/App.g.cs"],
        ignoredBuildOutputs: ["bin/Debug/app.exe"],
      },
      recommendedPins: ["Program.cs", "Game.csproj", "Game.cs", "Form1.Designer.cs", "tests/test_app.py"],
      counts: { totalFiles: 42, totalBytes: 123456, categories: {}, languages: ["C#: 4", "TypeScript: 2"] },
      summary: "E2E structure summary",
    };
    await route.fulfill(ok({
      ...structure,
      transcriptItem: {
        id: "e2e-structure",
        kind: "tool-structure",
        role: "tool",
        title: "分析專案檔案結構",
        content: "",
        createdAt: Date.now() / 1000,
        data: { structure },
      },
    }));
  });
  await page.route("**/api/pin-files", async (route) => {
    const body = route.request().postDataJSON?.() || {};
    await route.fulfill(ok({ pinnedFiles: body.files || [] }));
  });
  await page.route("**/api/file-tree?**", async (route) => {
    const url = new URL(route.request().url());
    const query = (url.searchParams.get("query") || "").toLowerCase();
    const items = Array.from({ length: 260 }, (_, index) => {
      const suffix = index % 3 === 0 ? "js" : index % 3 === 1 ? "py" : "css";
      return { path: `webui/static/js/sample-${String(index + 1).padStart(3, "0")}.${suffix}`, language: "JavaScript", kind: "text", size: 120 + index };
    }).filter((item) => !query || item.path.toLowerCase().includes(query));
    await route.fulfill(ok({ items: items.slice(0, 200), total: items.length, offset: 0, limit: 200 }));
  });
}

async function prepareReadyUi(page) {
  await page.evaluate(() => {
    const files = Array.from({ length: 260 }, (_, index) => `webui/static/js/sample-${String(index + 1).padStart(3, "0")}.${index % 2 ? "js" : "py"}`);
    window.CodeWorker.state.uiState = "ready";
    window.CodeWorker.state.summaryRaw = "E2E virtual tree project\n已同步釘選檔案：(無)";
    window.CodeWorker.elements.projectSummary.textContent = "E2E virtual tree project\n已同步釘選檔案：(無)";
    window.CodeWorker.tree.renderTree(files, files.length);
    window.CodeWorker.ui.setUiState("ready");
  });
}

test.describe("CodeWorker WebUI CodeGraph E2E", () => {
  test("runs CodeGraph and UI flows for three rounds", async ({ page, request }) => {
    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    await installCodeGraphMocks(page);
    await page.goto(WEBUI_URL);
    await page.waitForLoadState("domcontentloaded");
    await prepareReadyUi(page);
    await expect(page.locator("#codeGraphQueryInput")).toHaveCount(0);
    await expect(page.locator("#codeGraphUsePromptBtn")).toHaveText(/用目前輸入查 CodeGraph|Query CodeGraph from input/);
    await expect(page.locator("#chatInput")).toHaveAttribute("placeholder", /Form1|AudioManager|Program\.cs|build_project_rag_context/);

    for (let round = 1; round <= 3; round += 1) {
      await page.locator("#langEnBtn").click();
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      await page.locator("#langZhBtn").click();
      await expect(page.locator("html")).toHaveAttribute("lang", "zh-Hant");

      await page.locator("#analyzeBtn").click();
      await expect(page.locator("#chatLog")).toContainText("建議釘選");
      await expect(page.locator("#chatLog")).toContainText("Program.cs");
      await page.locator("#chatLog [data-structure-pin]").click();
      await expect(page.locator("#projectSummary")).toContainText("Program.cs");

      await page.locator("#chatInput").fill(`renderTree query round ${round}`);
      await page.locator("#codeGraphUsePromptBtn").click();
      await expect(page.locator("#chatLog")).toContainText("renderTree");
      await expect(page.locator("#chatLog")).toContainText(/無命中|no match/);
      await expect(page.locator("#chatLog")).toContainText("Form1");
      await page.locator("#chatLog .codegraph-chip").filter({ hasText: "Form1" }).last().click();
      await expect(page.locator("#chatLog")).toContainText("命中 symbols");
      await expect(page.locator("#chatLog")).toContainText("AudioManager.cs");
      await page.locator("#chatLog .codegraph-node").last().click();
      await expect(page.locator("#fileTreeSearch")).toHaveValue(/Form1\.cs|sample/);
      await page.locator("#codeGraphPinBtn").click();
      await expect(page.locator("#chatLog")).toContainText(/已釘選|Pinned/);
      await page.locator("#codeGraphRebuildBtn").click();
      await expect(page.locator("#chatLog")).toContainText(/重新掃描完成|Rescan complete/);
      await expect(page.locator("#chatLog")).toContainText(/nodes|Form1/);

      const scrollCheck = await page.evaluate(async (label) => {
        const log = document.querySelector("#chatLog");
        log.innerHTML = "";
        window.CodeWorker.ui.startChatAutoScroll();
        const live = window.CodeWorker.ui.appendLiveMessage("assistant", "start\n");
        for (let index = 0; index < 90; index += 1) {
          window.CodeWorker.ui.appendLiveText(live.content, `${label} follow line ${index}\n`);
        }
        await new Promise((resolve) => requestAnimationFrame(resolve));
        const followedInitial = log.scrollTop + log.clientHeight >= log.scrollHeight - 90;
        log.scrollTop = 0;
        log.dispatchEvent(new Event("scroll"));
        const manualTop = log.scrollTop;
        for (let index = 0; index < 30; index += 1) {
          window.CodeWorker.ui.appendLiveText(live.content, `${label} manual read line ${index}\n`);
        }
        await new Promise((resolve) => requestAnimationFrame(resolve));
        const stayedManual = log.scrollTop <= manualTop + 5;
        log.scrollTop = log.scrollHeight;
        log.dispatchEvent(new Event("scroll"));
        for (let index = 0; index < 20; index += 1) {
          window.CodeWorker.ui.appendLiveText(live.content, `${label} follow again line ${index}\n`);
        }
        await new Promise((resolve) => requestAnimationFrame(resolve));
        const followedAgain = log.scrollTop + log.clientHeight >= log.scrollHeight - 90;
        return { followedInitial, stayedManual, followedAgain };
      }, `round ${round}`);
      expect(scrollCheck.followedInitial).toBeTruthy();
      expect(scrollCheck.stayedManual).toBeTruthy();
      expect(scrollCheck.followedAgain).toBeTruthy();

      await page.evaluate((label) => window.CodeWorker.ui.setAiBusy(true, label), `AI E2E ${round}`);
      await expect(page.locator("#aiActivity")).toBeVisible();
      await page.evaluate(() => window.CodeWorker.ui.setAiBusy(false));
      await expect(page.locator("#aiActivity")).toBeHidden();

      await request.post(`${WEBUI_URL}/api/threads`, {
        data: { title: `UI 驗證 E2E ${round}`, metadata: { source: "webui-e2e" } },
      });
    }

    const cleanup = await request.post(`${WEBUI_URL}/api/threads/cleanup-empty`);
    expect(cleanup.ok()).toBeTruthy();
    expect((await cleanup.json()).data.deletedCount).toBeGreaterThanOrEqual(3);

    for (const width of VIEWPORTS) {
      await page.setViewportSize({ width, height: 918 });
      const metrics = await page.evaluate((expectedWidth) => {
        const rect = (selector) => {
          const el = document.querySelector(selector);
          const box = el ? el.getBoundingClientRect() : { width: 0, height: 0 };
          return { width: Math.round(box.width), height: Math.round(box.height) };
        };
        const overflowing = Array.from(document.querySelectorAll("button, select, input, textarea, .status, .ai-activity, .thread-title, .tree-link, h1, h2"))
          .filter((el) => {
            const style = getComputedStyle(el);
            return style.display !== "none" && style.visibility !== "hidden" && el.scrollWidth > el.clientWidth + 2;
          })
          .map((el) => `${el.tagName.toLowerCase()}#${el.id || ""}.${el.className || ""}`);
        return {
          width: expectedWidth,
          fileTree: rect("#fileTree"),
          codeGraph: rect("#codeGraphToolbar"),
          chatLog: rect("#chatLog"),
          overflowCount: overflowing.length,
          overflowing,
          renderedTreeRows: document.querySelectorAll("#fileTree .tree-item").length,
        };
      }, width);
      expect(metrics.fileTree.height).toBeGreaterThanOrEqual(width <= 1100 ? 360 : 260);
      expect(metrics.codeGraph.height).toBeGreaterThan(0);
      expect(metrics.chatLog.height).toBeGreaterThan(180);
      expect(metrics.overflowCount, metrics.overflowing.join(", ")).toBe(0);
      expect(metrics.renderedTreeRows).toBeLessThan(80);
    }
    expect(consoleErrors).toEqual([]);
  });
});
