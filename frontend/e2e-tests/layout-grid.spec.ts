/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect, Page } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";

const runUrl = getAppUrl("layout_grid.py//run");
const runMaxWidthUrl = getAppUrl("layout_grid_max_width.py//run");
const editUrl = getAppUrl("layout_grid.py//edit");

test("can run Grid layout", async ({ page }) => {
  await page.goto(runUrl);
  // wait 500ms to render
  await page.waitForTimeout(500);

  // Verify markdown "Grid Layout"
  await expect(page.getByText("Grid Layout")).toBeVisible();

  // Type in search box
  await page.getByRole("textbox").last().fill("hello");

  // Verify dependent output updated
  await expect(page.getByText("Searching hello")).toBeVisible();

  // Verify text 1 have the same y coordinate as text 2, but text 2 is further left
  const bb1 = await bbForText(page, "text 1");
  const bb2 = await bbForText(page, "text 2");
  expect(bb1.y).toBe(bb2.y);
  expect(bb1.x).toBeGreaterThan(bb2.x);

  await takeScreenshot(page, __filename);
});

test("can run Grid layout with max-width", async ({ page }) => {
  await page.goto(runMaxWidthUrl);
  // wait 500ms to render
  await page.waitForTimeout(500);

  // Verify markdown "Grid Layout"
  await expect(page.getByText("Grid Layout")).toBeVisible();

  await takeScreenshot(page, __filename);
});

test("can edit Grid layout", async ({ page }) => {
  await page.goto(editUrl);

  // Verify text 1 bounding box is above text 2
  let bb1 = await bbForText(page, "text 1");
  let bb2 = await bbForText(page, "text 2");
  expect(bb1.y).toBeLessThan(bb2.y);

  // Toggle preview-button
  await page.locator("#preview-button").click();
  // Wait 500ms to allow preview to render
  await page.waitForTimeout(500);

  // Verify text 1 have the same y coordinate as text 2, but text 2 is further left
  bb1 = await bbForText(page, "text 1");
  bb2 = await bbForText(page, "text 2");
  expect(bb1.y).toBe(bb2.y);
  expect(bb1.x).toBeGreaterThan(bb2.x);

  // Can still use interactive elements
  await page.getByRole("textbox").last().fill("hello");
  await expect(page.getByText("Searching hello")).toBeVisible();

  // Can toggle to Vertical layout
  const layoutSelect = page.getByTestId("layout-select");
  await expect(layoutSelect).toBeVisible();
  await layoutSelect.click();
  await page.getByText("Vertical").click();
  // Wait 500ms to allow preview to render
  await page.waitForTimeout(500);

  // Verify bounding boxes are back to vertical
  bb1 = await bbForText(page, "text 1");
  bb2 = await bbForText(page, "text 2");
  expect(bb1.x).toBe(bb2.x);
  expect(bb1.y).toBeLessThan(bb2.y);

  await takeScreenshot(page, __filename);
});

interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

function expectValidBoundingBox(
  bb: BoundingBox | null,
): asserts bb is BoundingBox {
  expect(bb).toBeDefined();
  if (!bb) {
    throw new Error("bb is null");
  }
  expect(bb.x).toBeGreaterThan(0);
  expect(bb.y).toBeGreaterThan(0);
  expect(bb.width).toBeGreaterThan(0);
  expect(bb.height).toBeGreaterThan(0);
}

async function bbForText(page: Page, text: string) {
  const el = page.getByText(text).first();
  await expect(el).toBeVisible();
  const bb = await el.boundingBox();
  expectValidBoundingBox(bb);
  return bb;
}
