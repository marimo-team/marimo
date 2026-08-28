/* Copyright 2026 Marimo. All rights reserved. */

import { expect, type Page, test } from "@playwright/test";
import { type ApplicationNames, getAppUrl } from "../playwright.config";
import { maybeRestartKernel } from "./helper";
import { waitForMarimoApp } from "./test-utils";

type VisualTheme = "light" | "dark";
type VisualView = "edit" | "read";

interface VisualCase {
  readonly app: ApplicationNames;
  readonly name: `${VisualView}-${VisualTheme}`;
  readonly theme: VisualTheme;
  readonly view: VisualView;
}

const DESKTOP_VIEWPORT = { width: 1280, height: 720 } as const;
const NARROW_VIEWPORT = { width: 390, height: 720 } as const;

const VISUAL_CASES = [
  {
    app: "visual_tokens.py",
    name: "edit-light",
    theme: "light",
    view: "edit",
  },
  {
    app: "visual_tokens.py",
    name: "edit-dark",
    theme: "dark",
    view: "edit",
  },
  {
    app: "visual_tokens.py//run",
    name: "read-light",
    theme: "light",
    view: "read",
  },
  {
    app: "visual_tokens.py//run",
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

async function resolveColor(page: Page, value: string): Promise<string> {
  return page.evaluate((cssValue) => {
    const probe = document.createElement("span");
    probe.style.color = cssValue;
    document.body.append(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  }, value);
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

  await expect(page.locator("select").first()).toBeVisible();

  const accentColor = await page.locator("html").evaluate(
    (element) => getComputedStyle(element).accentColor,
  );
  const primaryColor = await resolveColor(page, "var(--primary)");
  expect(accentColor).toBe(primaryColor);

  const semanticAliases =
    visualCase.theme === "light"
      ? [
          ["--ring", "hsl(215deg 20.2% 65.1%)"],
          ["--destructive", "var(--red-9)"],
          ["--destructive-hover", "var(--red-10)"],
          ["--destructive-border", "var(--red-11)"],
          ["--destructive-foreground", "var(--red-1)"],
          ["--error", "var(--red-9)"],
          ["--error-foreground", "var(--red-1)"],
          ["--success", "var(--grass-9)"],
          ["--success-hover", "var(--grass-10)"],
          ["--success-border", "var(--grass-11)"],
          ["--success-foreground", "var(--grass-1)"],
          ["--action", "var(--yellow-9)"],
          ["--action-hover", "var(--yellow-10)"],
          ["--action-border", "var(--yellow-11)"],
          ["--action-foreground", "var(--yellow-12)"],
        ]
      : [
          ["--ring", "var(--blue-8)"],
          ["--destructive", "var(--red-6)"],
          ["--destructive-hover", "var(--red-7)"],
          ["--destructive-border", "var(--red-11)"],
          ["--destructive-foreground", "var(--red-12)"],
          ["--error", "var(--red-6)"],
          ["--error-foreground", "var(--red-12)"],
          ["--success", "var(--grass-6)"],
          ["--success-hover", "var(--grass-7)"],
          ["--success-border", "var(--grass-11)"],
          ["--success-foreground", "var(--grass-12)"],
          ["--action", "var(--yellow-6)"],
          ["--action-hover", "var(--yellow-7)"],
          ["--action-border", "var(--yellow-11)"],
          ["--action-foreground", "var(--yellow-12)"],
        ];

  for (const [semanticToken, sourceColor] of semanticAliases) {
    const actualColor = await resolveColor(page, `var(${semanticToken})`);
    const expectedColor = await resolveColor(page, sourceColor);
    expect(actualColor, semanticToken).toBe(expectedColor);
  }

  for (const [label, semanticToken] of [
    ["Success", "--success-border"],
    ["Warning", "--action-border"],
    ["Danger", "--destructive-border"],
  ] as const) {
    const button = page.getByRole("button", { name: label });
    const colors = await button.evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        background: style.backgroundColor,
        border: style.borderColor,
      };
    });
    const expectedBorder = await resolveColor(
      page,
      `color-mix(in srgb, var(${semanticToken}), transparent 0%)`,
    );

    expect(colors.border, label).toBe(expectedBorder);
    expect(colors.border, label).not.toBe(colors.background);
  }
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

    await page.setViewportSize(NARROW_VIEWPORT);
    await page
      .getByRole("heading", { name: "Semantic token fixture" })
      .scrollIntoViewIfNeeded();
    await expect(page).toHaveScreenshot(
      `${visualCase.name}-390x720.png`,
      { mask },
    );
  });
}
