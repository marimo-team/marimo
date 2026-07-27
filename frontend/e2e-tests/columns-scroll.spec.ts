/* Copyright 2026 Marimo. All rights reserved. */
import type { Locator, Page } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { maybeRestartKernel, pressShortcut } from "./helper";

const appUrl = getAppUrl("columns.py");

/**
 * Repro for https://github.com/marimo-team/marimo/issues/10222
 *
 * These assert the target cell is in the viewport rather than that
 * `scrollLeft` moved: unfixed, the app still nudges a few pixels, which a
 * `scrollLeft > 0` check would accept.
 */

test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
    await maybeRestartKernel(page);
  }
});

/**
 * Returns the column 3 cell holding `far_away_variable = 42`, asserting it
 * starts off-screen so neither test can pass vacuously.
 */
async function setUpColumnsNotebook(page: Page): Promise<Locator> {
  await page.waitForLoadState("networkidle");

  const app = page.locator("#App");
  await expect(app).toHaveAttribute("data-config-width", "columns");

  // Go-to-definition resolves through the kernel's variable registry, so the
  // cells have to have run before the jump can find anything.
  await pressShortcut(page, "global.runStale");
  await expect(page.locator(".marimo-cell.needs-run")).toHaveCount(0, {
    timeout: 30_000,
  });

  const definitionCell = page
    .locator(".marimo-cell")
    .filter({ hasText: "far_away_variable = 42" });
  await expect(definitionCell).toHaveCount(1);
  await expect(definitionCell).not.toBeInViewport();

  return definitionCell;
}

test("jump to definition scrolls horizontally to an off-screen column", async ({
  page,
}) => {
  const definitionCell = await setUpColumnsNotebook(page);

  // Cmd/Ctrl + click the usage in column 0; its definition is in column 3.
  // Go-to-definition only arms on a modifier keydown, and only resolves a
  // target once a mousemove while the modifier is held has underlined the
  // token -- so drive keydown -> hover -> click explicitly.
  const modifier = process.platform === "darwin" ? "Meta" : "Control";
  const usage = page
    .locator(".cm-content")
    .first()
    .getByText("far_away_variable", { exact: true })
    .first();
  await expect(usage).toBeVisible();

  await page.keyboard.down(modifier);
  await usage.hover();

  // Guard: if the token never underlines, the click below is a no-op and the
  // test would fail for reasons unrelated to scrolling.
  await expect(page.locator(".underline").first()).toBeVisible();

  await usage.click();
  await page.keyboard.up(modifier);

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
