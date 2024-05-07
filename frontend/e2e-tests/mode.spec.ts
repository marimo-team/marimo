/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);

test("page renders edit feature in edit mode", async ({ page }) => {
  const appUrl = getAppUrl("title.py");
  await page.goto(appUrl);

  // 'title.py' to be in the document.
  expect(await page.getByText("title.py").count()).toBeGreaterThan(0);

  // Has elements with class name 'controls'
  expect(page.locator("#save-button")).toBeVisible();

  // Can see output
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();

  await takeScreenshot(page, __filename);
});

test.skip("can bring up the find/replace dialog", async ({ page }) => {
  const appUrl = getAppUrl("title.py");
  await page.goto(appUrl);

  // Wait for the cells to load
  await expect(page.locator("h1").getByText("Hello Marimo!")).toBeVisible();

  // Click mod+f to bring up the find/replace dialog
  // TODO: This is not working
  await page.keyboard.press("Meta+f", { delay: 200 });

  // Has placeholder text "Find"
  await expect(page.locator("[placeholder='Find']")).toBeVisible();

  await takeScreenshot(page, __filename);
});

test("can toggle to presenter mode", async ({ page }) => {
  const appUrl = getAppUrl("title.py");
  await page.goto(appUrl);

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

  await takeScreenshot(page, __filename);
});

test("page renders read only view in read mode", async ({ page }) => {
  const appUrl = getAppUrl("components.py");
  await page.goto(appUrl);

  // Filename is not visible
  await expect(page.getByText("components.py").last()).not.toBeVisible();
  // Has elements with class name 'controls'
  await expect(page.locator("#save-button")).toHaveCount(0);

  // Can see output
  await expect(page.locator("h1").getByText("UI Elements")).toBeVisible();

  await takeScreenshot(page, __filename);
});
