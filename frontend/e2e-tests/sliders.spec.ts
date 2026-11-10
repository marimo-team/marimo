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

for (const label of [
  "Repeating step",
  "Small range",
  "Decimal step",
  "Binary step",
  "Tiny step",
  "Editable value",
]) {
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
    for (const direction of [1, -1]) {
      for (let i = 1; i <= 60; i++) {
        const fraction = direction === 1 ? i / 60 : 1 - i / 60;
        await page.mouse.move(
          initialTrack.x + fraction * initialTrack.width,
          y,
        );
        const value = Number(await thumb.getAttribute("aria-valuenow"));
        const trackBox = await track.boundingBox();
        const thumbBox = await thumb.boundingBox();
        if (!trackBox || !thumbBox) {
          throw new Error("Slider bounds disappeared during dragging");
        }
        expect(Math.abs(trackBox.width - initialTrack.width)).toBeLessThan(0.5);
        expect(Math.abs(trackBox.x - initialTrack.x)).toBeLessThan(0.5);
        expect(direction * (value - previousValue)).toBeGreaterThanOrEqual(0);
        expect(direction * (thumbBox.x - previousX)).toBeGreaterThanOrEqual(
          -0.5,
        );
        previousValue = value;
        previousX = thumbBox.x;
      }
    }
    await page.mouse.up();
  });
}

test("a dropdown can reset the slider before further interaction", async ({
  page,
}) => {
  const thumb = page.getByRole("slider", {
    name: "Repeating step",
    exact: true,
  });
  await expect(thumb).toHaveAttribute("aria-valuenow", "0");
  const dropdown = page.locator("marimo-dropdown select");
  for (const [label, value] of [
    ["Middle", "30"],
    ["End", "60"],
    ["Start", "0"],
  ]) {
    await dropdown.selectOption({ label });
    await expect(thumb).toHaveAttribute("aria-valuenow", value);
  }
  await thumb.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => Number(await thumb.getAttribute("aria-valuenow")))
    .toBeCloseTo(1 / 30);
});

test("rounds the displayed value and tooltip without rounding the slider value", async ({
  page,
}) => {
  const thumb = page.getByRole("slider", {
    name: "Repeating step",
    exact: true,
  });
  await expect(thumb).toBeVisible();
  await thumb.focus();
  await page.keyboard.press("Home");
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => Number(await thumb.getAttribute("aria-valuenow")))
    .toBeCloseTo(1 / 30, 12);
  const plugin = page.locator("marimo-slider").filter({ has: thumb });
  await expect(plugin.getByText("0.03", { exact: true })).toBeVisible();
  await expect(page.getByRole("tooltip")).toHaveText("0.03");
});
