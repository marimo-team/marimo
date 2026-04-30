/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { waitForMarimoApp } from "./test-utils";

const appUrl = getAppUrl("streams.py");

test("stdout, stderr redirected to browser", async ({ page }) => {
  await page.goto(appUrl);
  await waitForMarimoApp(page);

  await expect(page).toHaveTitle("streams");
  await expect(page.getByText("streams.py")).toBeVisible();

  await expect(page.getByText(/^Hello, python!/)).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText(/^Hello, stdout!/)).toBeVisible({
    timeout: 10000,
  });
  await expect(page.getByText(/^Hello, stderr!/)).toBeVisible({
    timeout: 10000,
  });
});
