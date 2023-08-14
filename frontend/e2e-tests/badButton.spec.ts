/* Copyright 2023 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

const appUrl = getAppUrl("bad_button.py");

test("invalid on_click does not crash kernel", async ({ page }) => {
  await page.goto(appUrl);
  await page.getByRole("button", { name: "Bad button" }).click();
  // the kernel should still be alive
  await expect(page.getByText("kernel not found")).toHaveCount(0);
});
