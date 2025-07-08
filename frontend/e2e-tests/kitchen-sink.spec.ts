/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import {
  exportAsHTMLAndTakeScreenshot,
  exportAsPNG,
  takeScreenshot,
} from "./helper";

const _filename = fileURLToPath(import.meta.url);

const appUrl = getAppUrl("kitchen_sink.py");

test("can screenshot and download as html", async ({ page }) => {
  await page.goto(appUrl);

  await takeScreenshot(page, _filename);
  await exportAsHTMLAndTakeScreenshot(page);
});

test.skip("can screenshot and download as png", async ({ page }) => {
  await page.goto(appUrl);

  await exportAsPNG(page);
});
