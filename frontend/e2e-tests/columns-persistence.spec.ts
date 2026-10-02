/* Copyright 2026 Marimo. All rights reserved. */
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, type Page, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { pressShortcut } from "./helper";

const notebook = `import marimo

app = marimo.App(width="columns")


@app.cell(column=0)
def _():
    "left_first"
    return


@app.cell
def _():
    "left_second"
    return


@app.cell(column=1)
def _():
    "right_first"
    return


@app.cell
def _():
    "right_second"
    return


if __name__ == "__main__":
    app.run()
`;

let directory: string;
let filename: string;

test.beforeEach(async ({ page }) => {
  directory = await mkdtemp(path.resolve("e2e-tests/py/column-persistence-"));
  filename = path.join(directory, "notebook.py");
  await writeFile(filename, notebook);
  const url = new URL(getAppUrl("columns.py"));
  url.searchParams.set("file", filename);
  await page.goto(url.toString());
  await expect(page.locator(".cm-content")).toHaveCount(4);
});

test.afterEach(async ({ page }) => {
  // Shut down before removing files so the kernel can finish persisting its session.
  const shutdown = page.getByRole("button", { name: "Shutdown", exact: true });
  if (await shutdown.isVisible()) {
    await shutdownNotebook(page);
  }
  await page.close();
  await rm(directory, { recursive: true, force: true });
});

async function shutdownNotebook(page: Page) {
  await page.getByRole("button", { name: "Shutdown", exact: true }).click();
  await Promise.all([
    page.waitForResponse((response) =>
      response.url().endsWith("/api/kernel/shutdown"),
    ),
    page.getByRole("button", { name: "Confirm Shutdown" }).click(),
  ]);
}

async function setWidth(page: Page, width: string) {
  await page.getByTestId("app-config-button").click();
  await page.getByTestId("app-width-select").selectOption(width);
  await page.keyboard.press("Escape");
  await expect(page.locator("#App")).toHaveAttribute("data-config-width", width);
}

async function expectColumns(page: Page, columns: string[][]) {
  const renderedColumns = page.getByTestId(/^(cell-column|column-frame)$/);
  await expect(renderedColumns).toHaveCount(columns.length);
  for (const [index, cells] of columns.entries()) {
    await expect(renderedColumns.nth(index).locator(".cm-content")).toHaveText(
      cells.map((cell) => `"${cell}"`),
    );
  }
}

for (const width of ["compact", "medium", "full"]) {
  test(`preserves columns after saving and reloading in ${width} view`, async ({
    page,
  }) => {
    await setWidth(page, width);
    await expectColumns(page, [
      ["left_first", "left_second"],
      ["right_first", "right_second"],
    ]);
    await expect(
      page.getByRole("button", { name: "Python", exact: true }),
    ).toHaveCount(1);
    const positions = await page.locator(".marimo-cell").evaluateAll((cells) =>
      cells.map((cell) => {
        const { x, top, bottom } = cell.getBoundingClientRect();
        return { x, top, bottom };
      }),
    );
    const [first, second, third] = positions;
    if (!first || !second || !third) {
      throw new Error("Expected cells on both sides of the column boundary");
    }
    expect(second.x).toBeCloseTo(first.x, 0);
    expect(third.x).toBeCloseTo(first.x, 0);
    expect(second.top).toBeGreaterThan(first.bottom);
    expect(third.top - second.bottom).toBeCloseTo(second.top - first.bottom, 0);

    // An actual code edit exercises the notebook save path as well as config saving.
    await page.locator(".cm-content").last().fill('"right_edited"');
    await pressShortcut(page, "global.save");
    await expect.poll(() => readFile(filename, "utf8")).toContain('"right_edited"');
    const saved = await readFile(filename, "utf8");
    expect(saved.match(/@app.cell\(column=\d\)/g)).toEqual([
      "@app.cell(column=0)",
      "@app.cell(column=1)",
    ]);

    // Start a fresh kernel so the column layout must come from the saved file.
    await shutdownNotebook(page);
    await page.reload();
    await expect(page.locator("#App")).toHaveAttribute("data-config-width", width);
    await expectColumns(page, [
      ["left_first", "left_second"],
      ["right_first", "right_edited"],
    ]);
    await setWidth(page, "columns");
    await expectColumns(page, [
      ["left_first", "left_second"],
      ["right_first", "right_edited"],
    ]);
    await expect(page.getByTestId("column-header")).toHaveCount(2);
    const columnPositions = await page.getByTestId("column-frame").evaluateAll(
      (columns) => columns.map((column) => column.getBoundingClientRect().x),
    );
    expect(columnPositions[1]).toBeGreaterThan(columnPositions[0] ?? 0);

    // Switching repeatedly must not gradually flatten the saved layout.
    await setWidth(page, width);
    await setWidth(page, "columns");
    await expectColumns(page, [
      ["left_first", "left_second"],
      ["right_first", "right_edited"],
    ]);
  });
}

test("can drag across preserved column boundaries in compact view", async ({
  page,
}) => {
  await setWidth(page, "compact");
  const cell = page.locator(".marimo-cell").filter({ hasText: "left_second" });
  await cell.hover();
  const handle = cell.getByTestId("drag-button");
  const target = page.locator(".marimo-cell").filter({ hasText: "right_first" });
  const targetBox = await target.boundingBox();
  if (!targetBox) {
    throw new Error("Expected the destination cell to be visible");
  }
  await handle.hover();
  await page.mouse.down();
  await page.mouse.move(
    targetBox.x + targetBox.width / 2,
    targetBox.y + targetBox.height / 2,
    { steps: 10 },
  );
  await page.mouse.up();
  await expectColumns(page, [
    ["left_first"],
    ["left_second", "right_first", "right_second"],
  ]);
  await pressShortcut(page, "global.save");
  await expect.poll(() => readFile(filename, "utf8")).toMatch(
    /@app.cell\(column=1\)\s+def _\(\):\s+"left_second"/,
  );
  await shutdownNotebook(page);
  await page.reload();
  await setWidth(page, "columns");
  await expectColumns(page, [
    ["left_first"],
    ["left_second", "right_first", "right_second"],
  ]);
});

test("appends new cells to the last preserved column in compact view", async ({
  page,
}) => {
  await setWidth(page, "compact");
  await page.getByRole("button", { name: "Python", exact: true }).click();
  await expect(page.locator(".cm-content")).toHaveCount(5);
  await page.locator(".cm-content").last().fill('"new_last"');
  await pressShortcut(page, "global.save");
  await expect.poll(() => readFile(filename, "utf8")).toContain('"new_last"');
  await shutdownNotebook(page);
  await page.reload();
  await setWidth(page, "columns");
  await expectColumns(page, [
    ["left_first", "left_second"],
    ["right_first", "right_second", "new_last"],
  ]);
});
