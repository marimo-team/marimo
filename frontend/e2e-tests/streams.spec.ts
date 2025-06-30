/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

const appUrl = getAppUrl("streams.py");

test("stdout, stderr redirected to browser", async ({ page }) => {
  await page.goto(appUrl);

  await expect(page).toHaveTitle("streams");
  expect(page.getByText("streams.py")).toBeTruthy();

  // text printed using Python to be in the document.
  await expect(page.getByText(/^Hello, python!/)).toBeVisible();
  // text echoed to stdout, stderr to be in the document.
  await expect(page.getByText(/^Hello, stdout!/)).toBeVisible();
  await expect(page.getByText(/^Hello, stderr!/)).toBeVisible();
});
