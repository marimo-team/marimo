/* Copyright 2026 Marimo. All rights reserved. */
import { copyFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { openCellActions } from "./helper";

test("context menu shows and hides Markdown code after restoring focus", async ({ page }, testInfo) => {
  const filename = testInfo.outputPath("notebook.py");
  await copyFile("e2e-tests/py/title.py", filename);
  const url = new URL(getAppUrl("title.py"));
  url.searchParams.set("file", filename);
  await page.goto(url.toString());

  const title = page.getByRole("heading", { name: "Hello Marimo!", exact: true });
  const editor = page.getByTestId("cell-editor");
  await expect(title).toBeVisible();
  await openCellActions(page, title);
  await page.getByText("Convert to Markdown", { exact: true }).click();
  await page.keyboard.press("Escape");
  await page.locator("body").click({ position: { x: 4, y: 4 } });
  await expect(editor).toBeHidden();

  await title.click({ button: "right" });
  await page.getByRole("menuitem", { name: /^Show code/ }).click();
  await expect(editor).toBeVisible();
  await expect(editor.locator(".cm-content")).toBeFocused();

  await editor.locator(".cm-content").click({ button: "right" });
  await page.keyboard.press("Escape");
  await expect(editor.locator(".cm-content")).toBeFocused();

  await editor.locator(".cm-content").click({ button: "right" });
  await page.getByRole("menuitem", { name: /^Hide code/ }).click();
  await expect(editor).toBeHidden();
});
