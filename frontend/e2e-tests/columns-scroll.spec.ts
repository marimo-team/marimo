/* Copyright 2026 Marimo. All rights reserved. */
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { maybeRestartKernel, pressShortcut } from "./helper";

const appUrl = getAppUrl("columns.py");

/**
 * Asserts whether scrolling horizontally and vertically into view works as expected.
 */

test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
    await maybeRestartKernel(page);
  }
});

async function waitForCellsToRun(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");

  const app = page.locator("#App");
  await expect(app).toHaveAttribute("data-config-width", "columns");

  // Go-to-definition resolves through the kernel's variable registry, so the
  // cells have to have run before the jump can find anything.
  await pressShortcut(page, "global.runStale");
  await expect(page.locator(".marimo-cell.needs-run")).toHaveCount(0, {
    timeout: 30_000,
  });
}

/**
 * Locates the cell containing `text` and asserts it starts outside the
 * initial viewport along `axis`, so a later `toBeInViewport` assertion can't
 * pass vacuously.
 */
async function offScreenCell(
  page: Page,
  text: string,
  axis: "x" | "both",
): Promise<Locator> {
  const cell = page.locator(".marimo-cell").filter({ hasText: text });
  await expect(cell).toHaveCount(1);
  await expect(cell).not.toBeInViewport();

  const viewport = page.viewportSize();
  const box = await cell.boundingBox();
  if (!viewport || !box) {
    throw new Error(`could not measure the "${text}" cell`);
  }
  expect(box.x).toBeGreaterThanOrEqual(viewport.width);
  if (axis === "both") {
    expect(box.y).toBeGreaterThanOrEqual(viewport.height);
  }

  return cell;
}

/**
 * Returns the column 3 cell holding `far_away_variable = 42`, which starts
 * off-screen horizontally only.
 */
async function setUpColumnsNotebook(page: Page): Promise<Locator> {
  await waitForCellsToRun(page);
  return offScreenCell(page, "far_away_variable = 42", "x");
}

/**
 * Cmd/Ctrl + click a usage to jump to its definition. Go-to-definition only
 * arms on a modifier keydown, and only resolves a target once a mousemove
 * while the modifier is held has marked the token -- so drive
 * keydown -> hover -> click explicitly.
 *
 * Cross-cell jumps resolve through the kernel's variable registry. Waiting
 * for `.mo-cm-reactive-reference` (not the AST `.underline` fallback) is what
 * proves that registry is ready; without it the click arms but cannot find
 * the defining cell.
 */
async function jumpToDefinition(
  page: Page,
  variableName: string,
): Promise<void> {
  const usage = page
    .locator(".cm-content")
    .first()
    .locator(".mo-cm-reactive-reference")
    .getByText(variableName, { exact: true })
    .first();
  await expect(usage).toBeVisible({ timeout: 30_000 });

  const modifier = process.platform === "darwin" ? "Meta" : "Control";
  await page.keyboard.down(modifier);
  await usage.hover();

  // Guard: if the token never marks, the click below is a no-op and the
  // test would fail for reasons unrelated to scrolling.
  await expect(
    page.locator(".mo-cm-reactive-reference-hover").first(),
  ).toBeVisible();

  await usage.click();
  await page.keyboard.up(modifier);
}

test("jump to definition scrolls horizontally to an off-screen column", async ({
  page,
}) => {
  const definitionCell = await setUpColumnsNotebook(page);

  // Cmd/Ctrl + click the usage in column 0; its definition is in column 3.
  await jumpToDefinition(page, "far_away_variable");

  await expect(definitionCell).toBeInViewport({ ratio: 0.5 });
});

test("jump to definition scrolls both vertically and horizontally to an off-screen cell", async ({
  page,
}) => {
  await waitForCellsToRun(page);
  // Column 4 has a tall filler cell above this one, so it starts off-screen
  // below the fold as well as to the right -- unlike far_away_variable,
  // which only needs a horizontal scroll.
  const definitionCell = await offScreenCell(
    page,
    "deep_and_far_variable = 99",
    "both",
  );

  await jumpToDefinition(page, "deep_and_far_variable");

  await expect(definitionCell).toBeInViewport({ ratio: 0.5 });
});

test("find next scrolls horizontally to a match in an off-screen column", async ({
  page,
}) => {
  const definitionCell = await setUpColumnsNotebook(page);

  // Focus a cell so the cell-scoped find/replace shortcut applies.
  await page.locator(".cm-content").first().click();
  await pressShortcut(page, "cell.findAndReplace");

  const findInput = page.getByTestId("find-input");
  await expect(findInput).toBeVisible();
  await findInput.fill("far_away_variable");

  // Two matches in column 0, then the definition in column 3. Stepping
  // through the in-cell matches first is what looked like search being
  // "stuck": the selection advanced, but the viewport never followed.
  const findNext = page.getByTestId("find-next-button");
  await findNext.click();
  await findNext.click();
  await findNext.click();

  await expect(definitionCell).toBeInViewport({ ratio: 0.5 });
});
