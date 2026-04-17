/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import { openCellActions } from "./helper";
import { waitForMarimoApp } from "./test-utils";

const appUrl = getAppUrl("title.py");

test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  await waitForMarimoApp(page);
  if (info.retry) {
    await page.reload();
    await waitForMarimoApp(page);
  }
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
  await expect(page.getByText("Convert to Markdown")).toBeVisible();
  await page.getByText("Convert to Markdown").click();
  await expect(title).toBeVisible();

  // Expect cell editor to be invisible at first (markdown initial hide code is true)
  const cellEditor = page.getByTestId("cell-editor");
  await expect(cellEditor).toBeHidden({ timeout: 10000 });

  // Unhide code
  await openCellActions(page, title);
  await expect(page.getByText("Show code")).toBeVisible();
  await page.getByText("Show code").click();
  await expect(cellEditor).toBeVisible({ timeout: 10000 });

  // Hide code
  await openCellActions(page, title);
  await expect(page.getByText("Hide code")).toBeVisible();
  await page.getByText("Hide code").click();
  await expect(cellEditor).toBeHidden({ timeout: 10000 });
});
