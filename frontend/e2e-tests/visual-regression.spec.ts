/* Copyright 2026 Marimo. All rights reserved. */

import { expect, type Page, test } from "@playwright/test";
import { type ApplicationNames, getAppUrl } from "../playwright.config";
import { maybeRestartKernel } from "./helper";
import { waitForMarimoApp } from "./test-utils";

type VisualTheme = "light" | "dark";
type VisualView = "edit" | "read";

interface VisualCase {
  readonly app: ApplicationNames;
  readonly includeNarrow: boolean;
  readonly name: `${VisualView}-${VisualTheme}`;
  readonly theme: VisualTheme;
  readonly view: VisualView;
}

const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;
const NARROW_VIEWPORT = { width: 390, height: 720 } as const;

const VISUAL_CASES = [
  {
    app: "visual_tokens.py",
    includeNarrow: false,
    name: "edit-light",
    theme: "light",
    view: "edit",
  },
  {
    app: "visual_tokens.py",
    includeNarrow: true,
    name: "edit-dark",
    theme: "dark",
    view: "edit",
  },
  {
    app: "visual_tokens.py//run",
    includeNarrow: true,
    name: "read-light",
    theme: "light",
    view: "read",
  },
  {
    app: "visual_tokens.py//run",
    includeNarrow: false,
    name: "read-dark",
    theme: "dark",
    view: "read",
  },
] satisfies readonly VisualCase[];

function getThemedUrl(app: ApplicationNames, theme: VisualTheme): string {
  const url = new URL(getAppUrl(app));
  url.searchParams.set("theme", theme);
  return url.toString();
}

async function prepareVisualCase(
  page: Page,
  visualCase: VisualCase,
): Promise<void> {
  await page.setViewportSize(DESKTOP_VIEWPORT);
  await page.goto(getThemedUrl(visualCase.app, visualCase.theme));

  if (visualCase.view === "edit") {
    await maybeRestartKernel(page);
  } else {
    await waitForMarimoApp(page);
  }

  const heading = page.getByRole("heading", {
    name: "Semantic token fixture",
  });
  await expect(heading).toBeVisible();
  await heading.scrollIntoViewIfNeeded();

  await expect(page.locator("body")).toHaveAttribute(
    "data-theme",
    visualCase.theme,
  );
  await expect(page.locator("html")).toHaveCSS(
    "color-scheme",
    visualCase.theme,
  );
  await expect(page.locator("#App")).toHaveAttribute(
    "data-connection-state",
    "OPEN",
  );

  const saveButton = page.locator("#save-button");
  if (visualCase.view === "edit") {
    await expect(saveButton).toBeVisible();
  } else {
    await expect(saveButton).toHaveCount(0);
  }

  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await expect(page.locator(".marimo-output-loading")).toHaveCount(0);

  const focusedInput = page.getByTestId("marimo-plugin-text-input");
  await focusedInput.focus();
  await expect(focusedInput).toBeFocused();
}

for (const visualCase of VISUAL_CASES) {
  test(`${visualCase.view} view uses the ${visualCase.theme} theme`, async ({
    page,
  }) => {
    await prepareVisualCase(page, visualCase);

    const volatileMeters = page.locator(
      "[data-testid='memory-usage-bar'], " +
        "[data-testid='cpu-bar'], " +
        "[data-testid='gpu-bar']",
    );
    const mask = [volatileMeters];

    await expect(page).toHaveScreenshot(
      `${visualCase.name}-1280x720.png`,
      { mask },
    );

    if (visualCase.includeNarrow) {
      await page.setViewportSize(NARROW_VIEWPORT);
      await expect(page).toHaveScreenshot(
        `${visualCase.name}-390x720.png`,
        { mask },
      );
    }
  });
}
