/* Copyright 2024 Marimo. All rights reserved. */
import { test } from "@playwright/test";
import {
  exportAsHTMLAndTakeScreenshot,
  exportAsPNG,
  takeScreenshot,
} from "./helper";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);

test("can screenshot and download as html edit", async ({ page }) => {
  await page.goto("http://localhost:3000");

  // See text Initializing
  await page.waitForSelector("text=Initializing");
  // See text Welcome
  await page.waitForSelector("text=Welcome");

  await takeScreenshot(page, __filename);
  await exportAsHTMLAndTakeScreenshot(page);
});

test("can screenshot and download as html in run", async ({ page }) => {
  await page.goto("http://localhost:3000?mode=read");

  // See text Initializing
  await page.waitForSelector("text=Initializing");
  // See text Welcome
  await page.waitForSelector("text=Welcome");

  await takeScreenshot(page, __filename);
  await exportAsHTMLAndTakeScreenshot(page);
});
