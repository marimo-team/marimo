/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

test("it can clear and append output", async ({ page }) => {
  const appUrl = getAppUrl("output.py//run");
  await page.goto(appUrl);

  // Flakey: Test that Loading replaced exists at least once
  // await expect(page.getByText("Loading replace")).toBeVisible();
  // Now wait for Replaced to be visible
  await expect(page.getByText("Replaced!")).toBeVisible();
  // Test that Loading replaced does not exist
  await expect(page.getByText("Loading replace")).not.toBeVisible();

  // Test the end state of the output
  await expect(page.getByText("Appended!")).toBeVisible();
  await expect(page.getByText("Loading 0/5").first()).toBeVisible();
  await expect(page.getByText("Loading 4/5").first()).toBeVisible();

  // Test that Cleared does not exist
  await expect(page.getByText("Cleared!")).not.toBeVisible();

  // Test that Replaced by index is visible and To be replaced is not
  await expect(page.getByText("To be replaced.")).not.toBeVisible();
  await expect(page.getByText("Replaced by index!")).toBeVisible();

  await takeScreenshot(page, _filename);
});
