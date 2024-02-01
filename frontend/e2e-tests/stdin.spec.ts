/* Copyright 2024 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

const appUrl = getAppUrl("stdin.py//edit");

test("stdin works", async ({ page }) => {
  await page.goto(appUrl);

  expect(page.getByText("stdin.py")).toBeTruthy();

  // Check that "what is your name?" exists in the console
  await expect(page.getByTestId("console-output-area")).toHaveText(
    "what is your name?",
  );

  // Expect loading spinner
  await expect(page.getByTestId("loading-indicator")).toBeVisible();

  // Get input inside the console
  const consoleInput = page
    .getByTestId("console-output-area")
    .getByRole("textbox");
  // Type "marimo" into the console
  await consoleInput.fill("marimo");
  // Hit enter
  await consoleInput.press("Enter");

  // Check that "Hi, marimo" exists on the page
  await expect(page.getByText("Hi marimo")).toBeVisible();

  // Expect not loading spinner
  await expect(page.getByTestId("loading-indicator")).not.toBeVisible();
});
