/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import { openCellActions } from "./helper";

const appUrl = getAppUrl("title.py");

test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
  }
});

test.afterEach(async () => {
  // Need to reset the file because this test modifies it
  await resetFile("title.py");
});

test("change the cell to a markdown cell and hide code", async ({ page }) => {
  const title = page.getByText("Hello Marimo!", { exact: true });
  await expect(title).toBeVisible();

  // Convert to Markdown
  await openCellActions(page, title);
  await page.getByText("Convert to Markdown").click();
  await expect(title).toBeVisible();

  // Verify markdown content
  const markdown = page.getByText("import marimo as mo");
  await expect(markdown).toBeVisible();

  // Hide code
  await openCellActions(page, title);
  await page.getByText("Hide Code").click();
  await expect(title).toBeVisible();

  // Verify code editor is hidden
  const cellEditor = page.getByTestId("cell-editor");
  await expect(cellEditor).toBeHidden();
});
