/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import { exportAsHTMLAndTakeScreenshot, pressShortcut } from "./helper";

const appUrl = getAppUrl("cells.py");
test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
  }
});

test.beforeEach(async () => {
  // Need to reset the file because this test modifies it
  await resetFile("cells.py");
});

/**
 * Cell re-render count is a good indicator of performance.
 */
test("keeps re-renders from growing", async ({ page }) => {
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
  expect(cellRenderCount).toBe("8");
});

/**
 * This tests:
 *  - adding cells above and below existing cells.
 *  - running individual cells
 *  - moving cells up and down
 */
test("page renders 2 cells", async ({ page }) => {
  // Can see output / code
  await expect(page.locator("h1").getByText("Cell 1")).toBeVisible();
  await expect(page.locator("h1").getByText("Cell 2")).toBeVisible();

  // No add buttons are visible
  await expect(
    page.getByTestId("create-cell-button").locator(":visible").count(),
  ).resolves.toBe(0);

  // Hover over a cell the 'add cell' button appears
  await page.hover("text=Cell 1");
  await expect(
    page.getByTestId("create-cell-button").locator(":visible").count(),
  ).resolves.toBe(2);

  // Clicking the first button creates a new cell at the top
  await page
    .getByTestId("create-cell-button")
    .locator(":visible")
    .first()
    .click();
  // Type into the currently focused cell
  await page.locator("*:focus").fill(`mo.md("# Cell 0")`);

  // Check the rendered cells
  await expect(page.locator("h1")).toHaveText(["Cell 1", "Cell 2"]);

  // Run the new cell
  await page.getByTestId("run-button").locator(":visible").first().click();

  // Check the rendered cells
  await expect(page.locator("h1")).toHaveText(["Cell 0", "Cell 1", "Cell 2"]);

  // Add cell below, text, and run
  await page.hover("text=Cell 1");
  await page
    .getByTestId("create-cell-button")
    .locator(":visible")
    .last()
    .click();
  await page.locator("*:focus").fill(`mo.md("# Cell 1.5")`);
  await page.getByTestId("run-button").locator(":visible").last().click();

  // Verify the rendered cells
  await expect(page.locator("h1")).toHaveText([
    "Cell 0",
    "Cell 1",
    "Cell 1.5",
    "Cell 2",
  ]);

  // Focus on Cell 0 and move it down
  await page
    .getByRole("textbox")
    .filter({ hasText: 'mo.md("# Cell 0")' })
    .click();
  await pressShortcut(page, "cell.moveDown");

  // Focus on Cell 2 and move it up
  await page
    .getByRole("textbox")
    .filter({ hasText: 'mo.md("# Cell 2")' })
    .click();
  await pressShortcut(page, "cell.moveUp");

  // Verify the rendered cells
  await expect(page.locator("h1")).toHaveText([
    "Cell 1",
    "Cell 0",
    "Cell 2",
    "Cell 1.5",
  ]);

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
  await expect(page.locator("h1")).toHaveText(["Cell 1", "Cell 2"]);
});

test("export as HTML", async ({ page }) => {
  await exportAsHTMLAndTakeScreenshot(page);
});
