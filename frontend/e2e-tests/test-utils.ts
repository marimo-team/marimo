/* Copyright 2024 Marimo. All rights reserved. */

import type { Locator, Page } from "@playwright/test";

/**
 * Wait for a marimo app to be fully loaded and ready
 */
export async function waitForMarimoApp(
  page: Page,
  timeout = 30_000,
): Promise<void> {
  await page.waitForLoadState("networkidle", { timeout });

  // Wait for the marimo app to be initialized
  await page.waitForFunction(
    () => {
      // Check if the app is loaded by looking for key elements
      return (
        document.querySelector("[data-testid='cell-editor']") !== null ||
        document.querySelector(".marimo-cell") !== null ||
        document.querySelector("[data-testid='marimo-static']") !== null
      );
    },
    { timeout },
  );
}

/**
 * Wait for server to be responsive with retries
 */
export async function waitForServerReady(
  page: Page,
  url: string,
  maxRetries = 5,
): Promise<void> {
  let retries = 0;

  while (retries < maxRetries) {
    try {
      await page.goto(url, {
        waitUntil: "networkidle",
        timeout: 10_000,
      });

      // Additional check to ensure the page is actually loaded
      await waitForMarimoApp(page);
      return;
    } catch (error) {
      retries++;
      if (retries === maxRetries) {
        throw new Error(
          `Server not ready after ${maxRetries} retries: ${error}`,
        );
      }

      console.log(`Server not ready, retrying... (${retries}/${maxRetries})`);
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }
}

/**
 * Robust element interaction with retry
 */
export async function clickWithRetry(
  page: Page,
  selector: string,
  maxRetries = 3,
  timeout = 5000,
): Promise<void> {
  let element: Locator | undefined;
  for (let i = 0; i < maxRetries; i++) {
    try {
      element = page.locator(selector);
      await element.waitFor({ state: "visible", timeout });
      break;
    } catch (error) {
      if (i === maxRetries - 1) {
        throw error;
      }
      await page.waitForTimeout(1000);
    }
  }
  if (!element) {
    throw new Error(`Element not found: ${selector}`);
  }
  await element.click({ timeout });
}

export async function hoverWithRetry(
  page: Page,
  selector: string,
  maxRetries = 3,
  timeout = 5000,
): Promise<void> {
  let element: Locator | undefined;
  for (let i = 0; i < maxRetries; i++) {
    try {
      element = page.locator(selector);
      await element.waitFor({ state: "visible", timeout });
      break;
    } catch (error) {
      if (i === maxRetries - 1) {
        throw error;
      }
      await page.waitForTimeout(1000);
    }
  }
  if (!element) {
    throw new Error(`Element not found: ${selector}`);
  }
  await element.hover({ timeout });
}

/**
 * Safe page navigation with fallback
 */
export async function safeGoto(
  page: Page,
  url: string,
  timeout = 30_000,
): Promise<void> {
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout });
  } catch (error) {
    // Fallback to basic load
    console.log(`Network idle failed, trying basic load: ${error}`);
    await page.goto(url, { waitUntil: "load", timeout });
  }
}
