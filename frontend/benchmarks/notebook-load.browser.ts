/* Copyright 2026 Marimo. All rights reserved. */

// Times a notebook load in the editor, from navigation to a quiet main thread.
// node benchmarks/notebook-load.browser.ts URL OUTPUT_DIRECTORY
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

interface LoadProbe {
  /** [time, cells, editors] */
  samples: Array<[number, number, number]>;
  longTasks: Array<{ start: number; duration: number }>;
}

declare global {
  interface Window {
    loadProbe: LoadProbe;
  }
}

const [url, outputDirectory] = process.argv.slice(2);
if (!url || !outputDirectory) {
  throw new Error(
    "Usage: node benchmarks/notebook-load.browser.ts URL OUTPUT_DIRECTORY",
  );
}

const repetitions = Number(process.env.LOAD_BENCH_RUNS ?? 3);
const rates = (process.env.LOAD_BENCH_RATES ?? "1,4").split(",").map(Number);
const timeout = Number(process.env.LOAD_BENCH_TIMEOUT ?? 600_000);
const quietMs = 1500;
if (
  !Number.isInteger(repetitions) ||
  repetitions < 1 ||
  !Number.isFinite(timeout) ||
  timeout <= 0 ||
  rates.some((rate) => !Number.isFinite(rate) || rate < 1)
) {
  throw new Error(
    "Use positive integer repetitions, a positive timeout, and CPU slowdown rates of at least 1",
  );
}

const durations = [
  "TaskDuration",
  "ScriptDuration",
  "RecalcStyleDuration",
  "LayoutDuration",
];
const counters = ["RecalcStyleCount", "LayoutCount"];

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (let repetition = 1; repetition <= repetitions; repetition++) {
    for (const rate of rates) {
      const context = await browser.newContext({
        viewport: { width: 1280, height: 720 },
      });
      try {
        const page = await context.newPage();
        const errors: string[] = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.addInitScript(() => {
          const probe: LoadProbe = { samples: [], longTasks: [] };
          window.loadProbe = probe;
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              probe.longTasks.push({
                start: entry.startTime,
                duration: entry.duration,
              });
            }
          }).observe({ type: "longtask", buffered: true });
          // Live collections keep each sample cheap in a large document.
          const cells = document.getElementsByClassName("marimo-cell");
          const editors = document.getElementsByClassName("cm-editor");
          const sample = (now: number) => {
            probe.samples.push([now, cells.length, editors.length]);
            requestAnimationFrame(sample);
          };
          requestAnimationFrame(sample);
        });
        const cdp = await context.newCDPSession(page);
        await cdp.send("Performance.enable");
        await cdp.send("Emulation.setCPUThrottlingRate", { rate });
        const metrics = async () => {
          const result = await cdp.send("Performance.getMetrics");
          return new Map(result.metrics.map((m) => [m.name, m.value]));
        };
        const before = await metrics();
        await page.goto(url, { waitUntil: "commit" });
        await page.locator(".marimo-cell").first().waitFor({ timeout });
        // Editors mount one per task, so a quiet main thread alone is not the end.
        await page.waitForFunction(
          (quiet) => {
            const last = window.loadProbe.longTasks.at(-1);
            const idleFor =
              performance.now() - (last ? last.start + last.duration : 0);
            return (
              idleFor > quiet &&
              document.querySelectorAll(".cm-editor").length ===
                document.querySelectorAll(".marimo-cell").length &&
              !document.querySelector(
                '[data-status="running"], [data-status="queued"]',
              )
            );
          },
          quietMs,
          { timeout, polling: 250 },
        );
        const after = await metrics();
        const probe = await page.evaluate(() => window.loadProbe);
        const dom = await cdp.send("Memory.getDOMCounters");
        await cdp.send("HeapProfiler.collectGarbage");
        const heap = await cdp.send("Runtime.getHeapUsage");

        const [, cellCount, editorCount] = probe.samples.at(-1) ?? [0, 0, 0];
        const firstAt = (index: 1 | 2, count: number) =>
          probe.samples.find((sample) => sample[index] >= count)?.[0] ?? null;
        const lastLongTask = probe.longTasks.at(-1);
        const delta = (name: string) =>
          (after.get(name) ?? 0) - (before.get(name) ?? 0);
        const summary = {
          url,
          browser: browser.version(),
          rate,
          repetition,
          cellCount,
          units: "ms",
          firstCell: firstAt(1, 1),
          allCells: firstAt(1, cellCount),
          firstEditor: firstAt(2, 1),
          allEditors: firstAt(2, editorCount),
          mainThreadQuiet: lastLongTask
            ? lastLongTask.start + lastLongTask.duration
            : null,
          longTasks: {
            count: probe.longTasks.length,
            totalBlockingTime: probe.longTasks.reduce(
              (total, task) => total + Math.max(0, task.duration - 50),
              0,
            ),
            longest: Math.max(0, ...probe.longTasks.map((t) => t.duration)),
          },
          // Chrome reports durations in seconds.
          ...Object.fromEntries(
            durations.map((name) => [name, delta(name) * 1000]),
          ),
          ...Object.fromEntries(counters.map((name) => [name, delta(name)])),
          domNodes: dom.nodes,
          eventListeners: dom.jsEventListeners,
          heapUsedBytes: heap.usedSize,
          errors,
        };
        const filename = `load-cells-${cellCount}-cpu-${rate}-run-${repetition}.json`;
        await writeFile(
          path.join(outputDirectory, filename),
          `${JSON.stringify(summary, null, 2)}\n`,
        );
        process.stdout.write(`${JSON.stringify({ filename, ...summary })}\n`);
      } finally {
        await context.close();
      }
    }
  }
} finally {
  await browser.close();
}
