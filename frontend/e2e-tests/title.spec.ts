/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

const appUrl = getAppUrl("title.py");

test("can open url and see filename", async ({ page }) => {
  await page.goto(appUrl);

  // Expect a title equal to the file name.
  await expect(page).toHaveTitle("title");

  // 'title.py' to be in the document.
  expect(await page.getByText("title.py").count()).toBeGreaterThan(0);
});
