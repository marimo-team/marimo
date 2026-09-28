/* Copyright 2026 Marimo. All rights reserved. */

import fs from "node:fs/promises";
import path from "node:path";
import { expect, type Page, test } from "@playwright/test";

const homeUrl = "http://127.0.0.1:2718";
const savedNotebook = "e2e-tests/template-flow-output.py";
const savedNotebookPath = path.join(process.cwd(), savedNotebook);
const templateName = "Build an interactive control";
const featuredTemplateNames = [
  templateName,
  "Filter tabular data",
  "Query data with DuckDB",
];
const editedSource = 'import marimo as mo\ncopy_marker = "saved template copy"';

async function removeSavedNotebook() {
  await fs.rm(savedNotebookPath, { force: true });
}

async function openFeaturedTemplate(page: Page): Promise<Page> {
  const popup = page.waitForEvent("popup");
  await page
    .getByRole("button", { name: `Use template: ${templateName}` })
    .click();
  const templatePage = await popup;
  await expect(
    templatePage
      .getByRole("textbox")
      .filter({ hasText: 'label="Number of stars"' }),
  ).toBeVisible({ timeout: 15_000 });
  return templatePage;
}

test.beforeEach(removeSavedNotebook);
test.afterEach(removeSavedNotebook);

test("featured template opens, saves, reopens, and stays isolated", async ({
  page,
}) => {
  await page.goto(homeUrl);
  const templateCard = page.getByRole("button", {
    name: `Use template: ${templateName}`,
  });
  for (const name of featuredTemplateNames) {
    await expect(
      page.getByRole("button", { name: `Use template: ${name}` }),
    ).toBeVisible();
  }

  await page.route(
    "**/api/templates/interactive-controls/launch",
    async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Controlled launch failure" }),
      });
    },
  );
  await templateCard.click();
  await expect(page.getByText("Could not open template")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Create a new notebook" }),
  ).toBeVisible();
  await expect.poll(() => page.context().pages().length).toBe(1);
  await page.unroute("**/api/templates/interactive-controls/launch");

  const templatePage = await openFeaturedTemplate(page);
  const launchKey = new URL(templatePage.url()).searchParams.get("file");
  expect(launchKey).toMatch(/^__marimo_template__/);

  const editedCell = templatePage
    .getByRole("textbox")
    .filter({ hasText: "import marimo as mo" })
    .first();
  await editedCell.fill(editedSource);
  await editedCell.hover();
  const runResponse = templatePage.waitForResponse("**/api/kernel/run");
  await templatePage
    .getByTestId("run-button")
    .locator(":visible")
    .first()
    .click();
  expect((await runResponse).ok()).toBe(true);

  await templatePage.getByTestId("save-button").click();
  await expect(
    templatePage.getByRole("heading", { name: "Save notebook" }),
  ).toBeVisible();
  await templatePage.getByTestId("cancel-save-dialog-button").click();
  await expect(
    templatePage.getByRole("heading", { name: "Save notebook" }),
  ).toHaveCount(0);
  expect(new URL(templatePage.url()).searchParams.get("file")).toBe(launchKey);

  await templatePage.getByTestId("save-button").click();
  await templatePage.getByPlaceholder("filename").fill(savedNotebook);
  await templatePage
    .getByText(`Save as: ${path.basename(savedNotebook)}`)
    .click();
  await expect
    .poll(() => new URL(templatePage.url()).searchParams.get("file"))
    .toBe(savedNotebook);
  await expect.poll(async () => {
    try {
      return (await fs.readFile(savedNotebookPath, "utf8")).includes(
        "saved template copy",
      );
    } catch {
      return false;
    }
  }).toBe(true);
  await templatePage.close();

  await page.reload();
  await page.getByPlaceholder("Search").fill(path.basename(savedNotebook));
  const savedNotebookLink = page.locator(
    `a[href*="${encodeURIComponent(savedNotebook)}"]`,
  ).last();
  const reopenedPagePromise = page.waitForEvent("popup");
  await savedNotebookLink.click();
  const reopenedPage = await reopenedPagePromise;
  await expect(
    reopenedPage.getByRole("textbox").filter({ hasText: "saved template copy" }),
  ).toBeVisible({ timeout: 15_000 });
  await reopenedPage.close();

  const independentCopy = await openFeaturedTemplate(page);
  await expect(
    independentCopy
      .getByRole("textbox")
      .filter({ hasText: "saved template copy" }),
  ).toHaveCount(0);
  await independentCopy.close();
});
