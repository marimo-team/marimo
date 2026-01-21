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

  // Wait for slides mode - Swiper adds .swiper class and component has .mo-slides-theme
  const slidesContainer = page.locator(".swiper.mo-slides-theme");
  await expect(slidesContainer).toBeVisible();

  await takeScreenshot(page, __filename);

  // Check pagination shows we're on first slide (bullet 1 is active)
  // Use pagintion bullets instead of text because the library (Swiper) puts all elements in the viewport.
  const paginationBullets = page.locator(".swiper-pagination-bullet");
  await expect(paginationBullets.first()).toHaveClass(
    /swiper-pagination-bullet-active/,
  );

  // Navigate to next slide using right arrow key
  await page.keyboard.press("ArrowRight");

  // Verify we moved to second slide via pagination
  await expect(paginationBullets.nth(1)).toHaveClass(
    /swiper-pagination-bullet-active/,
  );

  await takeScreenshot(page, __filename);

  // Navigate back to first slide using left arrow key
  await page.keyboard.press("ArrowLeft");

  // Verify we're back on the first slide
  await expect(paginationBullets.first()).toHaveClass(
    /swiper-pagination-bullet-active/,
  );
});

test("slides fullscreen", async ({ page }) => {
  await openCommandPalette({ page, command: "Present as Slides" });

  // Wait for slides mode - Swiper adds .swiper class and component has .mo-slides-theme
  const slidesContainer = page.locator(".swiper.mo-slides-theme");
  await expect(slidesContainer).toBeVisible();

  // Test buttons
  await expect(page.getByText("Fullscreen")).toBeVisible();
  await page.getByText("Fullscreen").click();

  await expect(page.getByText("Exit Fullscreen")).toBeVisible();
  await page.getByText("Exit Fullscreen").click();

  await expect(page.getByText("Fullscreen")).toBeVisible();
  await page.getByText("Fullscreen").click();

  // Test Escape key for exiting fullscreen
  await page.keyboard.press("Escape");
  await expect(page.getByText("Fullscreen")).toBeVisible();
});
