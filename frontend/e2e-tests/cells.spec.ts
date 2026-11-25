/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import {
  exportAsHTMLAndTakeScreenshot,
  maybeRestartKernel,
  pressShortcut,
} from "./helper";

const appUrl = getAppUrl("cells.py");
test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
    await maybeRestartKernel(page);
  }
});

test.afterEach(async () => {
  // Need to reset the file because this test modifies it
  await resetFile("cells.py");
});

/**
 * Cell re-render count is a good indicator of performance.
 */
test.fixme("keeps re-renders from growing", async ({ page }) => {
  // The frontend build used by Playwright does not instrument render counts.
  await page.waitForLoadState("networkidle");

  // Read the render count
  const cellRenderCount = await page.evaluate(
    () => document.body.dataset.cellRenderCount,
  );

  // This count may grow with the addition of new features. If this is the case,
  // it is okay to increase the count. However, if the count is growing
  // unexpectedly, it is a sign that something is causing cells to re-render.
  // It is also ok to decrease the count if we find a way to reduce the number
  // of renders.
  expect(cellRenderCount).toBeDefined();
  expect(Number.parseInt(cellRenderCount || "", 10)).toBeLessThanOrEqual(6);
});

/**
 * This tests:
 *  - adding cells above and below existing cells.
 *  - running individual cells
 *  - moving cells up and down
 */
test("page renders 2 cells", async ({ page }) => {
  const cells = page.locator(".marimo-cell");
  const headings = page.getByRole("heading", { level: 1 });
  await expect(headings).toHaveText(["Cell 1", "Cell 2"]);

  const createButtons = page
    .getByTestId("create-cell-button")
    .locator(":visible");
  await expect(createButtons).toHaveCount(0);

  await page.getByRole("heading", { name: "Cell 1", exact: true }).hover();
  await expect(createButtons).toHaveCount(2);
  await createButtons.first().click();

  await expect(cells).toHaveCount(3);
  const firstEditor = cells.first().getByRole("textbox");
  await expect(firstEditor).toBeFocused();
  await firstEditor.fill(`mo.md("# Cell 0")`);
  await expect(headings).toHaveText(["Cell 1", "Cell 2"]);
  await pressShortcut(page, "cell.run");
  await expect(headings).toHaveText(["Cell 0", "Cell 1", "Cell 2"]);

  await page.getByRole("heading", { name: "Cell 1", exact: true }).hover();
  await expect(createButtons).toHaveCount(2);
  await createButtons.last().click();

  await expect(cells).toHaveCount(4);
  const middleEditor = cells.nth(2).getByRole("textbox");
  await expect(middleEditor).toBeFocused();
  await middleEditor.fill(`mo.md("# Cell 1.5")`);
  await pressShortcut(page, "cell.run");

  // Verify the rendered cells
  await expect(headings).toHaveText(["Cell 0", "Cell 1", "Cell 1.5", "Cell 2"]);

  // Focus on Cell 0 and move it down
  await cells
    .filter({ has: headings.getByText("Cell 0", { exact: true }) })
    .getByRole("textbox")
    .click();
  await pressShortcut(page, "cell.moveDown");

  // Focus on Cell 2 and move it up
  await cells
    .filter({ has: headings.getByText("Cell 2", { exact: true }) })
    .getByRole("textbox")
    .click();
  await pressShortcut(page, "cell.moveUp");

  // Verify the rendered cells
  await expect(headings).toHaveText(["Cell 1", "Cell 0", "Cell 2", "Cell 1.5"]);

  // Revert the file by deleting the new cells
  // Delete cell 1.5
  await page
    .getByRole("textbox")
    .filter({ hasText: 'mo.md("# Cell 1.5")' })
    .selectText();
  await page.keyboard.press("Backspace");
  await pressShortcut(page, "cell.delete");
  // Delete cell 0
  await page
    .getByRole("textbox")
    .filter({ hasText: 'mo.md("# Cell 0")' })
    .selectText();
  await page.keyboard.press("Backspace");
  await pressShortcut(page, "cell.delete");

  // Verify the rendered cells
  await expect(headings).toHaveText(["Cell 1", "Cell 2"]);
});

test("download as HTML", async ({ page }) => {
  await exportAsHTMLAndTakeScreenshot(page);
});
