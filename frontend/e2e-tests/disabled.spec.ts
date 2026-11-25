/* Copyright 2026 Marimo. All rights reserved. */

import { copyFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Locator, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { takeScreenshot } from "./helper";

const _filename = fileURLToPath(import.meta.url);

test("disabled cells", async ({ page }, info) => {
  // Use a new notebook path so this test can't resume a modified session.
  const fixture = "disabled_cells.py";
  const notebook = info.outputPath(fixture);
  await copyFile(path.join("e2e-tests", "py", fixture), notebook);
  const url = new URL(getAppUrl(fixture));
  url.searchParams.set("file", path.relative(process.cwd(), notebook));
  await page.goto(url.toString());

  const cells = page.locator(".marimo-cell");
  const firstCell = cells.nth(0);
  const secondCell = cells.nth(1);
  const runFirstCell = firstCell.getByTestId("run-button").first();
  const firstStatus = firstCell.getByTestId("cell-status");
  const secondStatus = secondCell.getByTestId("cell-status");
  const headings = page.getByRole("heading", { level: 1 });

  const setExecution = async (
    cell: Locator,
    action: "Disable execution" | "Enable execution",
  ) => {
    await cell.hover();
    await cell.getByTestId("cell-actions-button").click();
    await page.getByRole("option", { name: action }).click();
  };

  await expect(headings).toHaveText(["Cell 1", "Cell 2"]);
  await setExecution(firstCell, "Disable execution");
  await expect(firstStatus).toHaveAttribute("data-status", "disabled");
  await expect(secondStatus).toHaveAttribute(
    "data-status",
    "disabled-transitively",
  );

  await firstCell
    .getByRole("textbox")
    .fill('import marimo as mo\n\nmo.md("# Cell 1 updated")');
  const save = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith("/runtime/runs"),
  );
  await runFirstCell.click();
  expect((await save).ok()).toBe(true);
  await expect(headings).toHaveText(["Cell 1", "Cell 2"]);

  await expect(firstStatus).toHaveAttribute("data-status", "disabled");
  await expect(secondStatus).toHaveAttribute(
    "data-status",
    "disabled-transitively",
  );

  await setExecution(secondCell, "Disable execution");
  await expect(secondStatus).toHaveAttribute("data-status", "disabled");

  await setExecution(firstCell, "Enable execution");
  await runFirstCell.click();
  await expect(headings).toHaveText(["Cell 1 updated", "Cell 2"]);
  await expect(secondStatus).toHaveAttribute("data-status", "disabled");

  await setExecution(secondCell, "Enable execution");
  await secondCell.getByTestId("run-button").first().click();
  await expect(secondStatus).toHaveAttribute("data-status", "idle");

  await takeScreenshot(page, _filename);
});
