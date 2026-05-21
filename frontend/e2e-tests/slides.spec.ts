/* Copyright 2026 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { openCommandPalette, takeScreenshot } from "./helper";
import { waitForMarimoApp } from "./test-utils";

const __filename = fileURLToPath(import.meta.url);

const appUrl = getAppUrl("slides.py");
test.beforeEach(async ({ page }, info) => {
  await page.goto(appUrl);
  if (info.retry) {
    await page.reload();
  }

  // Wait for cells to appear
  await waitForMarimoApp(page);
});

test("slides", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Slides!" })).toBeVisible();

  await openCommandPalette({ page, command: "Present as Slides" });

  // Wait for slides mode - reveal.js adds .reveal class
  const slidesContainer = page.locator(".reveal.mo-slides-theme");
  await expect(slidesContainer).toBeVisible();

  await takeScreenshot(page, __filename);

  // Reveal.js marks the active slide <section> with `.present`. It only sets
  // `data-index-h` in overview / scroll modes, so we identify each slide
  // positionally via `.slides > section` and assert which one is active.
  const slides = slidesContainer.locator(".slides > section");
  await expect(slides).toHaveCount(2);
  await expect(slides.nth(0)).toHaveClass(/present/);

  // Click the deck so DOM focus lands on it (the wrapper is `tabindex="-1"`).
  // Without this, focus stays on whatever the command palette dialog
  // restored it to (often the speaker-notes textarea), which makes reveal
  // ignore the arrow keys.
  await slidesContainer.click();
  await expect
    .poll(() =>
      slidesContainer.evaluate((el) => document.activeElement === el),
    )
    .toBe(true);

  await page.keyboard.press("ArrowRight");
  await expect(slides.nth(1)).toHaveClass(/present/);

  await takeScreenshot(page, __filename);

  await page.keyboard.press("ArrowLeft");
  await expect(slides.nth(0)).toHaveClass(/present/);
});

test("slides fullscreen", async ({ page }) => {
  await openCommandPalette({ page, command: "Present as Slides" });

  // Wait for slides mode - reveal.js adds .reveal class
  const slidesContainer = page.locator(".reveal.mo-slides-theme");
  await expect(slidesContainer).toBeVisible();

  // Fullscreen button is hidden until hover
  const fullscreenButton = page.getByTestId("marimo-plugin-slides-fullscreen");
  const slidesWrapper = slidesContainer.locator("..");
  await slidesWrapper.hover();
  await expect(fullscreenButton).toBeVisible();

  // Enter fullscreen
  await fullscreenButton.click();

  // Exit fullscreen with Escape
  await page.keyboard.press("Escape");

  // Slides container should still be visible after exiting fullscreen
  await expect(slidesContainer).toBeVisible();
});
