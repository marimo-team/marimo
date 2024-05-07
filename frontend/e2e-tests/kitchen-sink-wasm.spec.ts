/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { exportAsHTMLAndTakeScreenshot, takeScreenshot } from "./helper";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);

test("can screenshot and download as html edit", async ({ page }) => {
  await page.goto("http://localhost:3000");

  // See text Initializing
  await expect(page.getByText("Initializing")).toBeVisible();
  // See text Welcome
  await expect(page.getByText("Welcome").first()).toBeVisible();

  await takeScreenshot(page, __filename);
  await exportAsHTMLAndTakeScreenshot(page);
});

test("can screenshot and download as html in run", async ({ page }) => {
  await page.goto("http://localhost:3000?mode=read");

  // See text Initializing
  await expect(page.getByText("Initializing")).toBeVisible();
  // See text Welcome
  await expect(page.getByText("Welcome").first()).toBeVisible();

  await takeScreenshot(page, __filename);
});
