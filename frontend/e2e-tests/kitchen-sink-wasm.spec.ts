/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { exportAsHTMLAndTakeScreenshot, takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

test.skip("can screenshot and download as html edit", async ({ page }) => {
  await page.goto("http://localhost:3000");

  // See text Initializing
  await expect(page.getByText("Initializing")).toBeVisible();
  // See text Welcome
  await expect(page.getByText("Welcome").first()).toBeVisible();

  await takeScreenshot(page, _filename);
  await exportAsHTMLAndTakeScreenshot(page);
});

test.skip("can screenshot and download as html in run", async ({ page }) => {
  await page.goto("http://localhost:3000?mode=read");

  // See text Initializing
  await expect(page.getByText("Initializing")).toBeVisible();
  // See text Welcome
  await expect(page.getByText("Welcome").first()).toBeVisible();

  await takeScreenshot(page, _filename);
});
