/* Copyright 2026 Marimo. All rights reserved. */
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

// #2515: a tooltip authored inside a disabled button's label must still show
// on hover, while the disabled button remains non-activatable.
test("tooltip works on a disabled button label (#2515)", async ({ page }) => {
  // A. Disabled button
  const disabledBtn = page.getByRole("button", { name: "Disabled button" });
  await expect(disabledBtn).toBeDisabled();

  // Tooltip is hidden until hover, then appears on hover.
  await expect(page.getByText("Why disabled")).toHaveCount(0);
  await disabledBtn.hover();
  await expect(page.getByText("Why disabled")).toBeVisible();

  // Force-clicking the disabled button does not trigger its on_click.
  await disabledBtn.click({ force: true });
  await expect(page.getByText("disabled value: 0")).toBeVisible();
  await expect(page.getByText("disabled value: 1")).toHaveCount(0);

  // B. Enabled control button
  const enabledBtn = page.getByRole("button", { name: "Enabled button" });
  await expect(enabledBtn).toBeEnabled();

  await enabledBtn.hover();
  await expect(page.getByText("Enabled tooltip")).toBeVisible();

  // A normal click increments its value.
  await enabledBtn.click();
  await expect(page.getByText("enabled value: 1")).toBeVisible();
});
