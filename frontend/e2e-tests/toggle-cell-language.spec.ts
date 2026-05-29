/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import { maybeRestartKernel, openCellActions } from "./helper";

const appUrl = getAppUrl("title.py");

test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
  }
  await maybeRestartKernel(page);
});

test.afterEach(async () => {
  // Need to reset the file because this test modifies it
  await resetFile("title.py");
});

test("change the cell to a markdown cell and toggle hide code", async ({
  page,
}) => {
  const title = page.getByText("Hello Marimo!", { exact: true });
  await expect(title).toBeVisible();

  // Convert to Markdown
  await openCellActions(page, title);
  await page.getByText("Convert to Markdown").click();
  await expect(title).toBeVisible();

  // Code stays visible while the cell is focused; blur it so the markdown
  // initial hide-code takes effect before asserting.
  await page.keyboard.press("Escape");
  await page.locator("body").click({ position: { x: 4, y: 4 } });

  // Expect cell editor to be invisible at first (markdown initial hide code is true)
  const cellEditor = page.getByTestId("cell-editor");
  await expect(cellEditor).toBeHidden();

  // Unhide code
  await openCellActions(page, title);
  await page.getByText("Show code").click();
  await expect(cellEditor).toBeVisible();

  // Hide code
  await openCellActions(page, title);
  await page.getByText("Hide code").click();
  await expect(cellEditor).toBeHidden();
});
