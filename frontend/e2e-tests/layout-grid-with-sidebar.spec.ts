/* Copyright 2024 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

const runUrl = getAppUrl("layout_grid_with_sidebar.py//run");
const editUrl = getAppUrl("layout_grid_with_sidebar.py//edit");

test("sidebar renders in run mode with grid layout", async ({ page }) => {
  await page.goto(runUrl);
  // wait 500ms to render
  await page.waitForTimeout(500);

  // Verify main content is visible
  await expect(page.getByText("Grid with Sidebar")).toBeVisible();
  await expect(page.getByText("Main Content Area")).toBeVisible();

  // Verify sidebar toggle button is visible
  const sidebarToggle = page.locator('[aria-label="Toggle sidebar"]').first();
  await expect(sidebarToggle).toBeVisible();

  // Click to open sidebar
  await sidebarToggle.click();
  await page.waitForTimeout(300);

  // Verify sidebar content is visible
  await expect(page.getByText("Sidebar Title")).toBeVisible();
  await expect(
    page.getByText("This sidebar should be visible in run mode"),
  ).toBeVisible();

  // Verify nav menu items are visible
  await expect(page.getByText("Section 1")).toBeVisible();
  await expect(page.getByText("Section 2")).toBeVisible();
  await expect(page.getByText("Section 3")).toBeVisible();

  await takeScreenshot(page, _filename);
});

test("sidebar renders in edit mode with grid layout preview", async ({
  page,
}) => {
  await page.goto(editUrl);
  // wait 500ms to render
  await page.waitForTimeout(500);

  // Toggle preview-button to enable grid layout
  await page.locator("#preview-button").click();
  await page.waitForTimeout(500);

  // Verify main content is visible
  await expect(page.getByText("Grid with Sidebar")).toBeVisible();

  // Verify sidebar toggle button is visible
  const sidebarToggle = page.locator('[aria-label="Toggle sidebar"]').first();
  await expect(sidebarToggle).toBeVisible();

  // Click to open sidebar
  await sidebarToggle.click();
  await page.waitForTimeout(300);

  // Verify sidebar content is visible
  await expect(page.getByText("Sidebar Title")).toBeVisible();

  await takeScreenshot(page, _filename);
});
