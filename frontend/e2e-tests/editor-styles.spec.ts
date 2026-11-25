/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

interface StyleProbe {
  editorStyleWrites: number;
  placeholderBars: number;
  animatedPlaceholderBars: number;
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
}) => {
  await page.addInitScript(() => {
    const probe: StyleProbe = {
      editorStyleWrites: 0,
      placeholderBars: 0,
      animatedPlaceholderBars: 0,
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
          for (const bar of node.querySelectorAll(".mo-code-placeholder-bar")) {
            probe.placeholderBars++;
            if (getComputedStyle(bar).animationName !== "none") {
              probe.animatedPlaceholderBars++;
            }
          }
        }
      }
    }).observe(document, { childList: true, subtree: true });
  });

  await page.goto(getAppUrl("many_cells.py"));
  await expect(page.locator(".cm-editor")).toHaveCount(CELL_COUNT);

  const probe = await page.evaluate(() => window.styleProbe);
  expect(probe.placeholderBars).toBeGreaterThan(0);
  expect(probe.animatedPlaceholderBars).toBe(0);
  expect(probe.editorStyleWrites).toBeLessThan(CELL_COUNT / 2);
});
