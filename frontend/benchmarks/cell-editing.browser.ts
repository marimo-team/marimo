/* Copyright 2026 Marimo. All rights reserved. */

// Run against a disposable notebook: this types into its middle cell.
// node benchmarks/cell-editing.browser.ts URL OUTPUT_DIRECTORY
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { installReactCommitRecorder } from "./react-commits.ts";

interface Sample {
  phase: string;
  handler: number;
  input: number;
  frame: number;
}

interface BrowserMetrics {
  phase: string;
  samples: Sample[];
  events: Array<{ phase: string; name: string; duration: number }>;
  longTasks: Array<{ phase: string; duration: number }>;
}

declare global {
  interface Window {
    editingMetrics: BrowserMetrics;
  }
}

const [url, outputDirectory] = process.argv.slice(2);
if (!url || !outputDirectory) {
  throw new Error(
    "Usage: node benchmarks/cell-editing.browser.ts URL OUTPUT_DIRECTORY",
  );
}

const repetitions = Number(process.env.EDITING_BENCH_RUNS ?? 3);
const continuousKeys = Number(process.env.EDITING_BENCH_CONTINUOUS_KEYS ?? 30);
const pausedKeys = 20;
const expectedKeys = continuousKeys + pausedKeys;
const warmup = " warmup";
const expectedHeadings = process.env.EDITING_BENCH_HEADINGS
  ? Number(process.env.EDITING_BENCH_HEADINGS)
  : undefined;
const headingSelector = ".marimo-cell :is(h1, h2, h3, h4, h5, h6)";
const rates = (process.env.EDITING_BENCH_RATES ?? "1,4,6")
  .split(",")
  .map(Number);
if (
  !Number.isInteger(repetitions) ||
  repetitions < 1 ||
  !Number.isInteger(continuousKeys) ||
  continuousKeys < 1 ||
  (expectedHeadings !== undefined &&
    (!Number.isInteger(expectedHeadings) || expectedHeadings < 0)) ||
  rates.some((rate) => !Number.isFinite(rate) || rate < 1)
) {
  throw new Error(
    "Use positive integer repetitions and key counts, nonnegative integer heading counts, and CPU slowdown rates of at least 1",
  );
}

function distribution(values: number[]) {
  const sorted = values.toSorted((a, b) => a - b);
  const quantile = (fraction: number) =>
    sorted[
      Math.min(sorted.length - 1, Math.ceil(sorted.length * fraction) - 1)
    ] ?? null;
  return {
    count: sorted.length,
    p50: quantile(0.5),
    p95: quantile(0.95),
    max: sorted.at(-1) ?? null,
  };
}

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (let repetition = 1; repetition <= repetitions; repetition++) {
    // Alternate order to reduce systematic warmup/order effects.
    for (const rate of repetition % 2 ? rates : rates.toReversed()) {
      const context = await browser.newContext({
        viewport: { width: 1280, height: 720 },
      });
      try {
        const page = await context.newPage();
        if (process.env.EDITING_BENCH_REACT === "1") {
          await installReactCommitRecorder(page);
        }
        const errors: string[] = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.goto(url);
        await page.locator(".cm-content").first().waitFor();
        const count = await page.locator(".marimo-cell").count();
        await page.waitForFunction(
          (expected) =>
            document.querySelectorAll(".cm-content").length === expected,
          count,
        );
        if (expectedHeadings !== undefined) {
          await page.waitForFunction(
            ({ selector, expected }) =>
              document.querySelectorAll(selector).length === expected,
            { selector: headingSelector, expected: expectedHeadings },
          );
        }
        await page.waitForFunction(
          () =>
            !document.querySelector(
              '[data-status="running"], [data-status="queued"]',
            ),
        );
        const headingCount = await page.locator(headingSelector).count();
        const editor = page.locator(".cm-content").nth(Math.floor(count / 2));
        await editor.focus();
        await editor.press("ControlOrMeta+End");
        const startingText = await editor.textContent();
        await page.keyboard.type(warmup);
        await page.waitForTimeout(2000);
        const originalText = await editor.textContent();

        await page.evaluate(() => {
          const metrics: BrowserMetrics = {
            phase: "continuous",
            samples: [],
            events: [],
            longTasks: [],
          };
          window.editingMetrics = metrics;
          window.editingCommits?.reset();
          const pending = new WeakMap<
            Event,
            { start: number; sample: Sample }
          >();
          let lastSample: Sample | undefined;
          let inputStart = 0;
          document.addEventListener(
            "keydown",
            (event) => {
              if (
                event.key !== "x" ||
                !(event.target instanceof HTMLElement) ||
                !event.target.closest(".cm-content")
              ) {
                return;
              }
              const start = performance.now();
              const sample = {
                phase: metrics.phase,
                handler: -1,
                input: -1,
                frame: -1,
              };
              lastSample = sample;
              metrics.samples.push(sample);
              pending.set(event, { start, sample });
              requestAnimationFrame(() => {
                // This callback precedes paint. Do not label this value INP.
                sample.frame = performance.now() - start;
              });
            },
            { capture: true },
          );
          document.addEventListener("keydown", (event) => {
            const value = pending.get(event);
            if (value) {
              value.sample.handler = performance.now() - value.start;
            }
          });
          document.addEventListener(
            "beforeinput",
            () => {
              inputStart = performance.now();
            },
            { capture: true },
          );
          document.addEventListener("input", () => {
            if (lastSample && inputStart) {
              lastSample.input = performance.now() - inputStart;
              inputStart = 0;
            }
          });
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              metrics.longTasks.push({
                phase: metrics.phase,
                duration: entry.duration,
              });
            }
          }).observe({ type: "longtask" });
          new PerformanceObserver((list) => {
            for (const entry of list.getEntries()) {
              metrics.events.push({
                phase: metrics.phase,
                name: entry.name,
                duration: entry.duration,
              });
            }
          }).observe({
            type: "event",
            durationThreshold: 16,
          } as PerformanceObserverInit);
        });
        const cdp = await context.newCDPSession(page);
        await cdp.send("Emulation.setCPUThrottlingRate", { rate });
        await page.waitForTimeout(500);
        const profile = process.env.EDITING_BENCH_PROFILE === "1";
        let traceComplete: Promise<{ stream?: string }> | undefined;
        if (profile) {
          traceComplete = new Promise((resolve) => {
            cdp.once("Tracing.tracingComplete", resolve);
          });
          await cdp.send("Tracing.start", {
            categories: "devtools.timeline,v8,blink.user_timing",
            transferMode: "ReturnAsStream",
          });
          await cdp.send("Profiler.enable");
          await cdp.send("Profiler.start");
        }
        // Real key events preserve CodeMirror's keyboard and DOM input paths.
        await page.keyboard.type("x".repeat(continuousKeys), { delay: 80 });
        await page.waitForTimeout(500);
        await page.evaluate(() => {
          window.editingMetrics.phase = "paused";
        });
        await page.keyboard.type("x".repeat(pausedKeys), { delay: 400 });
        await page.waitForTimeout(1000);
        const metrics = await page.evaluate(() => window.editingMetrics);
        const react = await page.evaluate(() => {
          const recorder = window.editingCommits;
          return recorder
            ? { version: recorder.version, commits: recorder.commits }
            : undefined;
        });
        if (
          react &&
          !react.commits.some((commit) => commit.renderDuration > 0)
        ) {
          throw new Error("Use the profiling build when EDITING_BENCH_REACT=1");
        }
        if (react && react.commits.length >= 1000) {
          throw new Error("React commit buffer filled; use a shorter run");
        }
        if (profile) {
          const result = await cdp.send("Profiler.stop");
          await writeFile(
            path.join(
              outputDirectory,
              `cells-${count}-cpu-${rate}-run-${repetition}.cpuprofile`,
            ),
            JSON.stringify(result.profile),
          );
          await cdp.send("Tracing.end");
          const trace = await traceComplete;
          if (!trace?.stream) {
            throw new Error("Chrome did not return a trace stream");
          }
          const chunks: string[] = [];
          while (true) {
            const chunk = await cdp.send("IO.read", { handle: trace.stream });
            chunks.push(
              chunk.base64Encoded
                ? Buffer.from(chunk.data, "base64").toString()
                : chunk.data,
            );
            if (chunk.eof) {
              break;
            }
          }
          await cdp.send("IO.close", { handle: trace.stream });
          await writeFile(
            path.join(
              outputDirectory,
              `cells-${count}-cpu-${rate}-run-${repetition}.trace.json`,
            ),
            chunks.join(""),
          );
        }
        const finalText = await editor.textContent();
        if (
          metrics.samples.length !== expectedKeys ||
          finalText !== `${originalText}${"x".repeat(expectedKeys)}` ||
          errors.length > 0
        ) {
          throw new Error(
            `Invalid run: ${JSON.stringify({ samples: metrics.samples.length, textMatches: finalText === `${originalText}${"x".repeat(expectedKeys)}`, errors })}`,
          );
        }
        const summary = {
          url,
          browser: browser.version(),
          cellCount: count,
          headingCount,
          rate,
          repetition,
          continuousKeys,
          pausedKeys,
          units: "ms",
          phases: ["continuous", "paused"].map((phase) => {
            const samples = metrics.samples.filter(
              (sample) => sample.phase === phase,
            );
            return {
              phase,
              keydownHandlers: distribution(
                samples
                  .filter((sample) => sample.handler >= 0)
                  .map((sample) => sample.handler),
              ),
              beforeInputToInputBubble: distribution(
                samples
                  .filter((sample) => sample.input >= 0)
                  .map((sample) => sample.input),
              ),
              keydownToAnimationFrame: distribution(
                samples.map((sample) => sample.frame),
              ),
              longTasks: distribution(
                metrics.longTasks
                  .filter((task) => task.phase === phase)
                  .map((task) => task.duration),
              ),
              // Event Timing omits events below its threshold and quantizes duration.
              slowEvents: distribution(
                metrics.events
                  .filter((event) => event.phase === phase)
                  .map((event) => event.duration),
              ),
            };
          }),
          metrics,
          react,
        };
        const filename = `cells-${count}-cpu-${rate}-run-${repetition}.json`;
        await writeFile(
          path.join(outputDirectory, filename),
          `${JSON.stringify(summary, null, 2)}\n`,
        );
        process.stdout.write(
          `${JSON.stringify({ filename, phases: summary.phases })}\n`,
        );
        // Restore the fixture so later runs have the same document size.
        await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
        for (let i = 0; i < expectedKeys + warmup.length; i++) {
          await page.keyboard.press("Backspace");
        }
        if ((await editor.textContent()) !== startingText) {
          throw new Error("Failed to restore the fixture");
        }
        await page.waitForTimeout(1500);
      } finally {
        await context.close();
      }
    }
  }
} finally {
  await browser.close();
}
