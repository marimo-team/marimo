/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { waitForMarimoApp } from "./test-utils";

const appUrl = getAppUrl("stdin.py");

test("stdin works", async ({ page }) => {
  await page.goto(appUrl);
  await waitForMarimoApp(page);

  await expect(page.getByText("stdin.py")).toBeVisible();

  // Check that "what is your name?" exists in the console
  await expect(page.getByTestId("console-output-area")).toContainText(
    "what is your name?",
  );

  // Get input inside the console
  const consoleInput = page
    .getByTestId("console-output-area")
    .getByRole("textbox");
  await consoleInput.fill("marimo");
  await consoleInput.press("Enter");

  // Check that "Hi marimo" exists on the page
  await expect(page.getByText("Hi marimo")).toBeVisible({ timeout: 10000 });

  // Expect no loading spinner after completion
  await expect(page.getByTestId("loading-indicator")).not.toBeVisible();
});
