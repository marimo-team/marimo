/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import { maybeRestartKernel, takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

const appUrl = getAppUrl("disabled_cells.py");
test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
    await maybeRestartKernel(page);
  }
});

test.afterEach(async () => {
  // Need to reset the file because this test modifies it
  await resetFile("disabled_cells.py");
});

test("disabled cells", async ({ page }) => {
  // Can see output / code
  await expect(page.locator("h1").getByText("Cell 1")).toBeVisible();
  await expect(page.locator("h1").getByText("Cell 2")).toBeVisible();

  // No add buttons are visible
  await expect(
    page.getByTestId("create-cell-button").locator(":visible"),
  ).toHaveCount(0);

  // Hover over a cell the drag button button appears
  // Click the drag button and then disable the cell
  await page.hover("text=Cell 1");
  await page.getByTestId("drag-button").locator(":visible").first().click();
  await page.getByText("Disable cell").click();

  // Check the cell status
  await expect(page.getByTitle("This cell is disabled")).toBeVisible();
  await expect(
    page.getByTitle("This cell has a disabled ancestor"),
  ).toBeVisible();
  await expect(
    page
      .getByTestId("cell-status")
      .first()
      .evaluate((el) => el.dataset.status),
  ).resolves.toBe("disabled");
  await expect(
    page
      .getByTestId("cell-status")
      .last()
      .evaluate((el) => el.dataset.status),
  ).resolves.toBe("disabled-transitively");

  // Add code to the first cell and save
  // The result should be stale
  await page.click(".cm-editor");
  await page.keyboard.type("\nx = 2");
  await page.getByTestId("run-button").locator(":visible").first().click();
  await expect(page.getByTitle("This cell is disabled")).toBeVisible();
  await expect(
    page.getByTitle("This cell has a disabled ancestor"),
  ).toBeVisible();
  await expect(
    page
      .getByTestId("cell-status")
      .first()
      .evaluate((el) => el.dataset.status),
  ).resolves.toBe("stale");
  await expect(
    page
      .getByTestId("cell-status")
      .last()
      .evaluate((el) => el.dataset.status),
  ).resolves.toBe("stale");

  // Disable the second cell
  await page.hover("text=Cell 2");
  await page.getByTestId("drag-button").locator(":visible").first().click();
  await page.getByText("Disable cell").click();

  // Check they are still stale
  await expect(page.getByTitle("This cell is disabled")).toHaveCount(2);
  await expect(
    page
      .getByTestId("cell-status")
      .first()
      .evaluate((el) => el.dataset.status),
  ).resolves.toBe("stale");
  await expect(
    page
      .getByTestId("cell-status")
      .last()
      .evaluate((el) => el.dataset.status),
  ).resolves.toBe("stale");

  // Enable the first
  await page.hover("text=Cell 1");
  await page.getByTestId("drag-button").locator(":visible").first().click();
  await page.getByText("Enable cell").click();

  // Check the status
  await expect(page.getByTitle("This cell is disabled")).toHaveCount(1);

  // Enable the second
  await page.hover("text=Cell 2");
  await page.getByTestId("drag-button").locator(":visible").first().click();
  await page.getByText("Enable cell").click();

  // Check the status
  await expect(page.getByTitle("This cell is disabled")).toHaveCount(0);

  await takeScreenshot(page, _filename);
});
