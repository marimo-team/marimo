/* Copyright 2023 Marimo. All rights reserved. */
import { test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import {
  exportAsHTMLAndTakeScreenshot,
  exportAsPNG,
  takeScreenshot,
} from "./helper";

test("can screenshot and export as html", async ({ page }) => {
  const appUrl = getAppUrl("kitchen_sink.py//edit");
  await page.goto(appUrl);

  await takeScreenshot(page, __filename);
  await exportAsHTMLAndTakeScreenshot(page);
  await exportAsPNG(page);
});
