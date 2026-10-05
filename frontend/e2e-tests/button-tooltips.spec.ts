/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

test.beforeEach(async ({ page }) => {
  await page.goto(getAppUrl("button_tooltips.py"));
});

test("disabled explanation is keyboard-accessible without allowing activation", async ({ page, browserName }) => {
  const button = page.getByRole("button", { name: "Run analysis" });
  const enabled = page.getByRole("button", { name: "Enabled action" });
  await expect(button).toHaveAttribute("aria-disabled", "true");
  await expect(button).not.toHaveAttribute("disabled");
  await enabled.focus();
  // WebKit on macOS uses Option-Tab to include buttons in keyboard navigation.
  await page.keyboard.press(browserName === "webkit" ? "Alt+Shift+Tab" : "Shift+Tab");
  await expect(button).toBeFocused();
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toHaveText("Select a dataset first");
  await expect(button).toHaveAttribute("aria-describedby", await tooltip.getAttribute("id") ?? "");
  await page.keyboard.press("Escape");
  await expect(tooltip).not.toBeVisible();
  await expect(button).toBeFocused();

  await page.keyboard.press("Enter");
  await page.keyboard.press("Space");
  await button.evaluate((element: HTMLButtonElement) => element.click());
  await page.keyboard.press("Control+l");
  await expect(page.getByText("Disabled count: 0; enabled count: 0")).toBeVisible();

  await page.keyboard.press(browserName === "webkit" ? "Alt+Tab" : "Tab");
  await expect(enabled).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Disabled count: 0; enabled count: 1")).toBeVisible();
});

test("explanation stays open when the pointer moves over it", async ({ page }) => {
  const button = page.getByRole("button", { name: "Run analysis" });
  await button.hover();
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toBeVisible();
  // Radix exposes role="tooltip" on a hidden description inside the popup.
  await tooltip.locator("..").hover();
  await expect(tooltip).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(tooltip).not.toBeVisible();
});
