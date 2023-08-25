/* Copyright 2023 Marimo. All rights reserved. */
import { Page, expect } from "@playwright/test";
import path from "node:path";

export async function createCellBelow(opts: {
  page: Page;
  cellSelector: string;
  content: string;
  run: boolean;
}) {
  const { page, cellSelector, content, run } = opts;

  // Hover over a cell the 'add cell' button appears
  await page.hover(cellSelector);
  await expect(
    page.getByTestId("create-cell-button").locator(":visible").count()
  ).resolves.toBe(2);

  // Clicking the first button creates a new cell below
  await page
    .getByTestId("create-cell-button")
    .locator(":visible")
    .last()
    .click();
  // Type into the currently focused cell
  if (content) {
    await page.locator("*:focus").type(content);
  }

  // Run the new cell
  if (run) {
    await page.locator("*:focus").hover();
    await page.getByTestId("run-button").locator(":visible").first().click();
  }
}

export async function runCell(opts: { page: Page; cellSelector: string }) {
  const { page, cellSelector } = opts;

  // Hover over a cell
  await page.hover(cellSelector);

  // Run the new cell
  await page.getByTestId("run-button").locator(":visible").first().click();
}

const countsForName: Record<string, number> = {};
/**
 * Take a screenshot of the page.
 * @example
 * await takeScreenshot(page, __filename);
 */
export async function takeScreenshot(page: Page, filename: string) {
  const clean = path.basename(filename).replace(".spec.ts", "");

  const count = countsForName[clean] || 0;
  countsForName[clean] = count + 1;
  const fullName = `${clean}.${count}`;
  await page.screenshot({
    path: `e2e-tests/screenshots/${fullName}.png`,
    fullPage: true,
  });
}
