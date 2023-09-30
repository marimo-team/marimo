/* Copyright 2023 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";

test("it can clear and append output", async ({ page }) => {
  const appUrl = getAppUrl("output.py//run");
  await page.goto(appUrl);

  // Test that Loading replaced exists at least once
  await expect(page.getByText("Loading replace")).toBeVisible();
  // Now wait for Replaced to be visible
  await expect(page.getByText("Replaced!")).toBeVisible();
  // Test that Loading replaced does not exist
  await expect(page.getByText("Loading replace")).not.toBeVisible();

  // Test the end state of the output
  await expect(page.getByText("Appended!")).toBeVisible();
  await expect(page.getByText("Loading 0/5")).toBeVisible();
  await expect(page.getByText("Loading 4/5")).toBeVisible();

  // Test that Cleared does not exist
  await expect(page.getByText("Cleared!")).not.toBeVisible();

  await takeScreenshot(page, __filename);
});
