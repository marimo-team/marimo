/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { createCellBelow, runCell } from "./helper";

const appUrl = getAppUrl("bugs.py");
test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
  }
});

/**
 * This test makes sure that downstream UI elements are re-initialized when
 * upstream source cells are re-run.
 */
test("correctly initializes cells", async ({ page }, info) => {
  // Is initialized to 1
  const number = page
    .getByTestId("marimo-plugin-number-input")
    .locator("input");
  await expect(number).toBeVisible();
  await expect(number.inputValue()).resolves.toBe("1");

  // Change the value to 5
  await number.fill("5");
  await number.blur();

  // Create a new cell, add `bug_1` to it, and run it
  await createCellBelow({
    page,
    cellSelector: "text=bug 1",
    content: `bug_1`,
    run: true,
  });

  // Check they are both 5
  let numberInputs = page
    .getByTestId("marimo-plugin-number-input")
    .locator("input");
  await expect(numberInputs).toHaveCount(2);
  await expect(numberInputs.first()).toHaveValue("5");
  await expect(numberInputs.last()).toHaveValue("5");

  // Run first cell
  await runCell({ page, cellSelector: "text=bug 1" });

  // Check each number input is 1
  numberInputs = page
    .getByTestId("marimo-plugin-number-input")
    .locator("input");
  await expect(numberInputs).toHaveCount(2);
  await expect(numberInputs.first()).toHaveValue("1");
  await expect(numberInputs.last()).toHaveValue("1");
});
