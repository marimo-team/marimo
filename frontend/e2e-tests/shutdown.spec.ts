/* Copyright 2023 Marimo. All rights reserved. */
import { test, expect } from "@playwright/test";
import { getAppUrl, startServer } from "../playwright.config";
import { takeScreenshot } from "./helper";

test("shutdown shows disconnected text", async ({ page }) => {
  const appUrl = getAppUrl("shutdown.py");
  await page.goto(appUrl);
  await page.getByRole("button", { name: "Shutdown" }).click();
  // TODO(akshayka): there's some kind of timing bug; just wait
  // a small amount of time for now as a hack
  await new Promise((resolve) => setTimeout(resolve, 100));
  // confirm shutdown on modal
  await page.getByRole("button", { name: "Confirm Shutdown" }).click();

  // kernel disconnected message to be on the page
  await expect(page.getByText("kernel not found")).toBeVisible();

  // when no unsaved changes, recovery modal should not be shown
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Download unsaved changes?")).toHaveCount(0);

  // when changes are made, recovery modal should be shown
  await page
    .getByRole("textbox")
    .filter({ hasText: "print('123')" })
    .type("1234");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Download unsaved changes?")).toHaveCount(1);

  await takeScreenshot(page, __filename);
});

test.afterAll(async () => {
  startServer("shutdown.py"); // restart the server
});
