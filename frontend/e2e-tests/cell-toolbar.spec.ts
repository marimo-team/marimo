/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "@playwright/test";
import { getAppUrl, resetFile } from "../playwright.config";
import { pressShortcut } from "./helper";
import { waitForMarimoApp } from "./test-utils";

const appUrl = getAppUrl("cells.py");

test.beforeEach(async ({ page }) => {
  await page.goto(appUrl);
  await waitForMarimoApp(page);
  await expect(page.locator("h1").getByText("Cell 2")).toBeVisible();
});

test.afterEach(async () => {
  await resetFile("cells.py");
});

for (const key of ["Enter", "Space"]) {
  test(`${key} activates the focused run button once`, async ({ page }) => {
    const cell = page.locator(".marimo-cell").first();
    const runButton = cell.getByTestId("run-button").first();
    await cell.hover();
    await expect(runButton).toBeEnabled();
    await runButton.focus();
    await expect(runButton).toBeFocused();

    const runs: string[] = [];
    page.on("request", (request) => {
      if (request.url().endsWith("/api/kernel/run")) {
        runs.push(request.postData() ?? "");
      }
    });
    const response = page.waitForResponse("**/api/kernel/run");
    await page.keyboard.press(key);
    expect((await response).ok()).toBe(true);
    await expect(runButton).toBeEnabled();
    expect(runs).toHaveLength(1);
  });
}

test("modified run shortcuts still work from a toolbar button", async ({ page }) => {
  const cell = page.locator(".marimo-cell").first();
  const runButton = cell.getByTestId("run-button").first();
  await cell.hover();
  await expect(runButton).toBeEnabled();
  await cell.getByTestId("cell-actions-button").focus();
  const response = page.waitForResponse("**/api/kernel/run");
  await pressShortcut(page, "cell.run");
  expect((await response).ok()).toBe(true);
  await expect(page.getByPlaceholder("Search actions...")).not.toBeVisible();
});

test("Enter on the cell itself still focuses its editor", async ({ page }) => {
  const cell = page.locator(".marimo-cell").first();
  await cell.focus();
  await page.keyboard.press("Enter");
  await expect(cell.locator(".cm-content").first()).toBeFocused();
});
