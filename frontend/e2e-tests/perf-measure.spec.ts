/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { getAppUrl } from "../playwright.config";

const _filename = fileURLToPath(import.meta.url);

const metricsToObject = (res: {
  metrics: Array<{ name: string; value: number }>;
}) => Object.fromEntries(res.metrics.map((m) => [m.name, m.value]));

const appUrl = () => {
  const url = getAppUrl("large-notebook.py");
  return process.env.PROFILE === "1" ? `${url}&profile=1` : url;
};

test("perf snapshot: load + scroll", async ({ page }) => {
  test.setTimeout(120_000);

  const consoleLines: string[] = [];
  page.on("console", (msg) => consoleLines.push(msg.text()));

  const client = await page.context().newCDPSession(page);
  await client.send("Performance.enable");

  const t0 = Date.now();
  await page.goto(appUrl());
  await page.waitForFunction(
    () => document.querySelectorAll("[data-cell-id]").length >= 100,
    undefined,
    { timeout: 60_000 },
  );
  await page.waitForFunction(
    () =>
      document.querySelectorAll('[data-status="running"], [data-status="queued"]')
        .length === 0,
    undefined,
    { timeout: 60_000 },
  );
  const loadMs = Date.now() - t0;
  const loadMetrics = metricsToObject(await client.send("Performance.getMetrics"));

  // Scroll top → bottom → top via wheel (real scroll cost, not instant scrollTo)
  await page.mouse.move(400, 300);
  for (let i = 0; i < 60; i++) {
    await page.mouse.wheel(0, 400);
    await page.waitForTimeout(20);
  }
  await page.mouse.move(400, 300);
  for (let i = 0; i < 60; i++) {
    await page.mouse.wheel(0, -400);
    await page.waitForTimeout(20);
  }
  const scrollMetrics = metricsToObject(await client.send("Performance.getMetrics"));

  const domCount = await page.evaluate(
    () => document.querySelectorAll("[data-cell-id]").length,
  );
  expect(domCount).toBeGreaterThan(0); // sanity only — never a perf gate

  // Navigate away so web-vitals emits the final INP report, then capture it
  const assetsDir = join(dirname(_filename), "../../marimo/_static/assets")
  await page.goto("about:blank");
  await page.waitForTimeout(300);

  const chunkBytes = readdirSync(assetsDir)
    .filter((f) => f.endsWith(".js"))
    .reduce((sum, f) => sum + statSync(join(assetsDir, f)).size, 0);

  const delta = (name: string) =>
    (scrollMetrics[name] - loadMetrics[name]).toFixed(1);
  console.log(
    "PERF_RESULT " +
      JSON.stringify(
        {
          loadMs,
          loadScriptingMs: loadMetrics.ScriptDuration.toFixed(1),
          loadLayoutMs: loadMetrics.LayoutDuration.toFixed(1),
          scrollScriptingMs: delta("ScriptDuration"),
          scrollLayoutMs: delta("LayoutDuration"),
          scrollTaskMs: delta("TaskDuration"),
          domCount,
          chunkBytes,
          vitals: consoleLines.filter((l) => l.includes("[Metric")),
        },
        null,
        2,
      ),
  );
});
