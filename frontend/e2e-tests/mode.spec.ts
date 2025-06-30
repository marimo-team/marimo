/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { type BrowserContext, expect, type Page, test } from "@playwright/test";
import {
  type ApplicationNames,
  getAppMode,
  getAppUrl,
} from "../playwright.config";
import { maybeRestartKernel, takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

async function gotoPage(
  app: ApplicationNames,
  page: Page,
  context: BrowserContext,
) {
  const url = getAppUrl(app);
  const mode = getAppMode(app);

  await page.goto(url);

  // Verify is has loaded
  if (mode === "edit") {
    await maybeRestartKernel(page);
  }
}

// Re-use page for all tests
let page: Page;
test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
});
test.afterAll(async () => {
  await page.close();
});

test.skip("page renders edit feature in edit mode", async ({ context }) => {
  await gotoPage("title.py", page, context);

  // 'title.py' to be in the document.
  expect(await page.getByText("title.py").count()).toBeGreaterThan(0);

  // Has elements with class name 'controls'
  expect(page.locator("#save-button")).toBeVisible();

  // Can see output
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();

  await takeScreenshot(page, _filename);
});

test.skip("can bring up the find/replace dialog", async ({ context }) => {
  await gotoPage("title.py", page, context);

  // Wait for the cells to load
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();

  // Click mod+f to bring up the find/replace dialog
  // TODO: This is not working
  await page.keyboard.press("Meta+f", { delay: 200 });

  // Has placeholder text "Find"
  await expect(page.locator("[placeholder='Find']")).toBeVisible();

  await takeScreenshot(page, _filename);
});

test("can toggle to presenter mode", async ({ context }) => {
  await gotoPage("title.py", page, context);

  // Can see output and code
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();
  await expect(page.getByText("# Hello Marimo!")).toBeVisible();

  // Toggle preview-button
  await page.locator("#preview-button").click();

  // Can see output
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();
  // No code
  await expect(page.getByText("# Hello Marimo!")).not.toBeVisible();

  // Toggle preview-button again
  await page.locator("#preview-button").click();

  // Can see output and code
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();
  await expect(page.getByText("# Hello Marimo!")).toBeVisible();

  await takeScreenshot(page, _filename);
});

test("page renders read only view in read mode", async ({ context }) => {
  await gotoPage("components.py", page, context);

  // Filename is not visible
  await expect(page.getByText("components.py").last()).not.toBeVisible();
  // Has elements with class name 'controls'
  await expect(page.locator("#save-button")).toHaveCount(0);

  // Can see output
  await expect(page.locator("h1").getByText("UI Elements")).toBeVisible();

  await takeScreenshot(page, _filename);
});
