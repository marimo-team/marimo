/* Copyright 2026 Marimo. All rights reserved. */
import { copyFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { openCommandPalette } from "./helper";

interface StyleProbe {
  editorStyleWrites: number;
  placeholders: number;
  animatedPlaceholders: number;
}

declare global {
  interface Window {
    styleProbe: StyleProbe;
  }
}

const CELL_COUNT = 20;

/**
 * Restyling the document once per cell makes loading a large notebook
 * quadratic, so the work done while editors mount must not grow with cells.
 */
test("mounting editors does not restyle the document per cell", async ({
  page,
}, testInfo) => {
  await page.addInitScript(() => {
    const placeholderSelector = '[data-testid="cell-editor-placeholder"]';
    const probe: StyleProbe = {
      editorStyleWrites: 0,
      placeholders: 0,
      animatedPlaceholders: 0,
    };
    window.styleProbe = probe;
    new MutationObserver((records) => {
      for (const { target, addedNodes } of records) {
        // CodeMirror's generated class names start with "ͼ".
        if (target.nodeName === "STYLE" && target.textContent?.includes("ͼ")) {
          probe.editorStyleWrites++;
        }
        for (const node of addedNodes) {
          if (!(node instanceof Element)) {
            continue;
          }
          const placeholders = node.matches(placeholderSelector)
            ? [node]
            : node.querySelectorAll(placeholderSelector);
          for (const placeholder of placeholders) {
            probe.placeholders++;
            if (
              placeholder
                .getAnimations({ subtree: true })
                .some((animation) => animation instanceof CSSAnimation)
            ) {
              probe.animatedPlaceholders++;
            }
          }
        }
      }
    }).observe(document, { childList: true, subtree: true });
  });

  const filename = testInfo.outputPath("many_cells.py");
  await copyFile("e2e-tests/py/many_cells.py", filename);
  const url = new URL(getAppUrl("many_cells.py"));
  url.searchParams.set("file", filename);
  await page.goto(url.toString());

  const cells = page.locator(".marimo-cell");
  await expect(cells).toHaveCount(CELL_COUNT);
  await openCommandPalette({ page, command: "Show all markdown code" });

  for (const cell of await cells.all()) {
    await cell.scrollIntoViewIfNeeded();
    await expect(cell.locator(".cm-editor")).toBeVisible();
  }
  await expect(page.locator(".cm-editor")).toHaveCount(CELL_COUNT);

  const probe = await page.evaluate(() => window.styleProbe);
  expect(probe.placeholders).toBeGreaterThan(0);
  expect(probe.animatedPlaceholders).toBe(0);
  expect(probe.editorStyleWrites).toBeLessThan(CELL_COUNT / 2);
});
