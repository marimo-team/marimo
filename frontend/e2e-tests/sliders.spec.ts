/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { pressShortcut } from "./helper";
import { waitForMarimoApp } from "./test-utils";

test.beforeEach(async ({ page }) => {
  await page.goto(getAppUrl("sliders.py"));
  await waitForMarimoApp(page);
  await pressShortcut(page, "global.runStale");
});

for (const label of ["Repeating step", "Editable value"]) {
  test(`${label} keeps its track stable while dragging`, async ({ page }) => {
    const thumb = page.getByRole("slider", { name: label, exact: true });
    await expect(thumb).toBeVisible();
    await thumb.scrollIntoViewIfNeeded();
    await thumb.focus();
    await page.keyboard.press("Home");
    await expect(thumb).toHaveAttribute("aria-valuenow", "0");
    const plugin = page.locator("marimo-slider").filter({ has: thumb });
    const track = plugin.getByTestId("track");
    const initialTrack = await track.boundingBox();
    const initialThumb = await thumb.boundingBox();
    if (!initialTrack || !initialThumb) {
      throw new Error("Slider must have measurable track and thumb bounds");
    }

    const y = initialThumb.y + initialThumb.height / 2;
    await page.mouse.move(initialThumb.x + initialThumb.width / 2, y);
    await page.mouse.down();

    let previousValue = 0;
    let previousX = initialThumb.x;
    for (const fraction of [0.01, 0.2, 0.6, 1]) {
      await page.mouse.move(initialTrack.x + fraction * initialTrack.width, y);
      const value = Number(await thumb.getAttribute("aria-valuenow"));
      const trackBox = await track.boundingBox();
      const thumbBox = await thumb.boundingBox();
      if (!trackBox || !thumbBox) {
        throw new Error("Slider bounds disappeared during dragging");
      }
      expect(Math.abs(trackBox.width - initialTrack.width)).toBeLessThan(0.5);
      expect(Math.abs(trackBox.x - initialTrack.x)).toBeLessThan(0.5);
      expect(value).toBeGreaterThan(previousValue);
      expect(thumbBox.x).toBeGreaterThan(previousX);
      previousValue = value;
      previousX = thumbBox.x;
    }
    await page.mouse.up();
  });
}
