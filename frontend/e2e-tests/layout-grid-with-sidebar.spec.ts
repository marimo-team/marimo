/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

const runUrl = getAppUrl("layout_grid_with_sidebar.py//run");

test("sidebar renders in run mode with grid layout", async ({ page }) => {
  await page.goto(runUrl);
  // wait 500ms to render
  await page.waitForTimeout(500);

  // Verify main content is visible
  await expect(page.getByText("Grid with Sidebar").last()).toBeVisible();
  await expect(page.getByText("Main Content Area").last()).toBeVisible();

  // Verify sidebar content is visible
  await expect(page.getByText("Sidebar Title").first()).toBeVisible();
  await expect(
    page.getByText("This sidebar should be visible in run mode").first(),
  ).toBeVisible();

  // Verify nav menu items are visible
  await expect(page.getByText("Section 1").first()).toBeVisible();
  await expect(page.getByText("Section 2").first()).toBeVisible();
  await expect(page.getByText("Section 3").first()).toBeVisible();

  await takeScreenshot(page, _filename);
});
