/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

const appUrl = getAppUrl("bad_button.py");

test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
  }
});

test("invalid on_click does not crash kernel", async ({ page }) => {
  await page.getByRole("button", { name: "Bad button" }).click();
  // the kernel should still be alive
  await expect(page.getByText("kernel not found")).toHaveCount(0);
});
