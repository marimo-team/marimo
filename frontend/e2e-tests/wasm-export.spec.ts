/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "@playwright/test";

const mirrorURL = process.env.MARIMO_WASM_MIRROR_URL;
const offlineURL = process.env.MARIMO_WASM_OFFLINE_URL;

test.describe("static WASM exports", () => {
  test.setTimeout(120_000);

  test("runs a mirror-backed export", async ({ page }) => {
    test.skip(!mirrorURL, "Set MARIMO_WASM_MIRROR_URL to run this test");

    await page.goto(mirrorURL!);
    const button = page.getByRole("button", { name: "Increment" });
    await expect(button).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText("Count: 0")).toBeVisible();
    await button.click();
    await expect(page.getByText("Count: 1")).toBeVisible();
  });

  test("runs an offline export", async ({ page }) => {
    test.skip(!offlineURL, "Set MARIMO_WASM_OFFLINE_URL to run this test");

    const failedRequests: string[] = [];
    page.on("requestfailed", (request) => {
      failedRequests.push(request.url());
    });
    await page.goto(offlineURL!);
    const button = page.getByRole("button", { name: "Increment" });
    await expect(button).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText("Count: 0")).toBeVisible();
    await button.click();
    await expect(page.getByText("Count: 1")).toBeVisible();
    expect(failedRequests).toEqual([]);
  });
});
