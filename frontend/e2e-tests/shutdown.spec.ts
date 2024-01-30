/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl, startServer } from "../playwright.config";
import { takeScreenshot } from "./helper";

test("can resume a session", async ({ page }) => {
  const appUrl = getAppUrl("shutdown.py");
  await page.goto(appUrl);

  await expect(page.getByText("None", { exact: true })).toBeVisible();
  // type in the form
  await page.locator("#output-Hbol").getByRole("textbox").fill("12345");
  // shift enter to run the form
  await page.keyboard.press("Meta+Enter");

  // wait for the output to appear
  let secondCell = await page.locator(".Cell").nth(1);
  await expect(secondCell.getByText("12345")).toBeVisible();
  await expect(secondCell.getByText("54321")).toBeVisible();

  // Refresh the page
  await page.reload();

  await expect(
    page.getByText("You have reconnected to an existing session.")
  ).toBeVisible();
  secondCell = await page.locator(".Cell").nth(1);
  await expect(page.getByText("12345")).toBeVisible();
  await expect(page.getByText("54321")).toBeVisible();
});

test("restart kernel", async ({ page }) => {
  const appUrl = getAppUrl("shutdown.py");
  await page.goto(appUrl);

  await page.getByTestId("notebook-menu-dropdown").click();
  await page.getByText("Restart kernel").click();
  await page.getByLabel("Confirm Restart").click();

  await expect(page.getByText("None", { exact: true })).toBeVisible();
});

test("shutdown shows disconnected text", async ({ page }) => {
  const appUrl = getAppUrl("shutdown.py");
  await page.goto(appUrl);
  await page.getByRole("button", { name: "Shutdown" }).click();
  // confirm shutdown on modal
  await page.getByRole("button", { name: "Confirm Shutdown" }).click();

  // kernel disconnected message to be on the page
  await expect(page.getByText("kernel not found")).toBeVisible();

  // when no unsaved changes, recovery modal should not be shown
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Download unsaved changes?")).toHaveCount(0);

  // when changes are made, recovery modal should be shown
  await page
    .getByRole("textbox")
    .filter({ hasText: "import marimo" })
    .fill("1234");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Download unsaved changes?")).toHaveCount(1);

  await takeScreenshot(page, __filename);
});

test.afterAll(() => {
  startServer("shutdown.py"); // restart the server
});
