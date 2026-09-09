/* Copyright 2026 Marimo. All rights reserved. */

import { expect, type Page, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { waitForMarimoApp } from "./test-utils";

const appUrl = getAppUrl("visual_tokens.py//run");

function cssTimeToMilliseconds(value: string): number {
  const firstValue = value.split(",", 1)[0];
  return firstValue.endsWith("ms")
    ? Number.parseFloat(firstValue)
    : Number.parseFloat(firstValue) * 1000;
}

async function resolveSystemColor(page: Page, value: string): Promise<string> {
  return page.evaluate((cssValue) => {
    const probe = document.createElement("span");
    probe.style.color = cssValue;
    probe.style.forcedColorAdjust = "none";
    document.body.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  }, value);
}

test("reduces motion in the marimo namespace", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(appUrl);
  await waitForMarimoApp(page);

  const styles = await page.locator(".marimo").first().evaluate((root) => {
    const probe = document.createElement("div");
    probe.className = "animate-spin transition-all duration-300";
    root.append(probe);
    const runningAppIcon = document.createElement("div");
    runningAppIcon.className = "running-app-icon";
    root.append(runningAppIcon);
    const style = getComputedStyle(probe);
    const runningAppIconStyle = getComputedStyle(runningAppIcon);
    const result = {
      animationDelay: style.animationDelay,
      animationDuration: style.animationDuration,
      animationIterationCount: style.animationIterationCount,
      scrollBehavior: style.scrollBehavior,
      transitionDelay: style.transitionDelay,
      transitionDuration: style.transitionDuration,
      runningAppIconAnimationName: runningAppIconStyle.animationName,
      runningAppIconVisibility: runningAppIconStyle.visibility,
    };
    probe.remove();
    runningAppIcon.remove();
    return result;
  });

  expect(cssTimeToMilliseconds(styles.animationDuration)).toBeLessThanOrEqual(
    0.01,
  );
  expect(cssTimeToMilliseconds(styles.transitionDuration)).toBeLessThanOrEqual(
    0.01,
  );
  expect(cssTimeToMilliseconds(styles.animationDelay)).toBe(0);
  expect(cssTimeToMilliseconds(styles.transitionDelay)).toBe(0);
  expect(styles.animationIterationCount).toBe("1");
  expect(styles.scrollBehavior).toBe("auto");
  expect(styles.runningAppIconAnimationName).toBe("none");
  expect(styles.runningAppIconVisibility).toBe("visible");
});

test("uses visible system colors for control states", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await page.goto(appUrl);
  await waitForMarimoApp(page);

  const buttonFace = await resolveSystemColor(page, "ButtonFace");
  const buttonText = await resolveSystemColor(page, "ButtonText");
  const grayText = await resolveSystemColor(page, "GrayText");
  const highlight = await resolveSystemColor(page, "Highlight");
  const highlightText = await resolveSystemColor(page, "HighlightText");

  const button = page.getByRole("button", { name: "Neutral" });
  await expect(button).toBeVisible();

  const defaultColors = await button.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      background: style.backgroundColor,
      border: style.borderColor,
      text: style.color,
    };
  });
  expect(defaultColors).toEqual({
    background: buttonFace,
    border: buttonText,
    text: buttonText,
  });

  await button.hover();
  await expect
    .poll(() =>
      button.evaluate((element) => {
        const style = getComputedStyle(element);
        return {
          background: style.backgroundColor,
          text: style.color,
        };
      }),
    )
    .toEqual({ background: highlight, text: highlightText });

  const disabledButton = page.getByTestId("forced-colors-disabled-button");
  await button.evaluate((element) => {
    const clone = element.cloneNode(true) as HTMLButtonElement;
    clone.disabled = true;
    clone.dataset.testid = "forced-colors-disabled-button";
    element.parentElement?.append(clone);
  });
  const disabledColors = await disabledButton.evaluate((element) => {
    const style = getComputedStyle(element);
    return { border: style.borderColor, text: style.color };
  });
  expect(disabledColors).toEqual({ border: grayText, text: grayText });

  const input = page.getByTestId("marimo-plugin-text-input");
  await page.keyboard.press("Tab");
  await input.focus();
  await expect(input).toBeFocused();
  const focusOutline = await input.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      color: style.outlineColor,
      style: style.outlineStyle,
      width: style.outlineWidth,
    };
  });
  expect(focusOutline.style).toBe("solid");
  expect(focusOutline.width).toBe("2px");
  expect(focusOutline.color).not.toBe("rgba(0, 0, 0, 0)");
});
