/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test, type Locator } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { openCommandPalette } from "./helper";
import { waitForMarimoApp } from "./test-utils";

async function measureLayout(deck: Locator) {
  return deck.evaluate((el) => {
    const canvas = el.querySelector<HTMLElement>(".slides");
    const content = canvas?.querySelector<HTMLElement>(
      "section.present .mo-slide-content",
    );
    const scroll = canvas?.querySelector<HTMLElement>(
      "section.present [data-testid='slide-scroll-container']",
    );
    const paragraph = content?.querySelector<HTMLElement>(".paragraph, p");
    const formula = content
      ?.querySelector("marimo-tex")
      ?.shadowRoot?.querySelector<HTMLElement>(".katex-html");
    if (!canvas || !content || !scroll || !paragraph || !formula) {
      throw new Error("Slide content is not ready");
    }
    const scale = canvas.getBoundingClientRect().width / canvas.offsetWidth;
    return {
      canvas: { width: canvas.offsetWidth, height: canvas.offsetHeight },
      content: { width: content.offsetWidth, height: content.offsetHeight },
      paragraph: {
        width: paragraph.offsetWidth,
        height: paragraph.offsetHeight,
      },
      formula: { width: formula.offsetWidth, height: formula.offsetHeight },
      overflowing:
        scroll.scrollHeight > scroll.clientHeight + 1 ||
        scroll.scrollWidth > scroll.clientWidth + 1,
      fitsViewport:
        canvas.getBoundingClientRect().width <= el.clientWidth + 1 &&
        canvas.getBoundingClientRect().height <= el.clientHeight + 1,
      scale,
    };
  });
}

test("slides preserve layout when the viewport and fullscreen state change", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });
  await page.goto(getAppUrl("slides_sizing.py"));
  await waitForMarimoApp(page);
  await openCommandPalette({ page, command: "Re-run all cells" });
  await expect(
    page.getByRole("heading", { name: "Resolution-independent slides" }),
  ).toBeVisible();
  await openCommandPalette({ page, command: "Present as Slides" });

  const deck = page.locator(".reveal.mo-slides-theme");
  await expect(deck.locator("section.present .katex-html")).toBeVisible();
  await page.evaluate(() => document.fonts.ready);

  const initial = await measureLayout(deck);
  expect(initial.canvas.width / initial.canvas.height).toBeCloseTo(16 / 9, 2);
  expect(initial.overflowing).toBe(false);
  expect(initial.fitsViewport).toBe(true);

  const { scale: initialScale, ...initialLayout } = initial;
  const sidebar = page.getByRole("complementary", {
    name: "Slide configuration",
  });
  await sidebar.getByRole("button", { name: "Collapse panel" }).click();
  await expect
    .poll(async () => {
      const { scale, ...layout } = await measureLayout(deck);
      return { layout, grew: scale > initialScale };
    })
    .toEqual({ layout: initialLayout, grew: true });
  await sidebar.getByRole("button", { name: "Expand panel" }).click();
  await expect
    .poll(async () => (await measureLayout(deck)).scale)
    .toBeCloseTo(initialScale, 2);

  for (const viewport of [
    { width: 1024, height: 768 },
    { width: 800, height: 600 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport);
    await expect
      .poll(async () => {
        const { scale, ...layout } = await measureLayout(deck);
        return { layout, scaleChanged: Math.abs(scale - initialScale) > 0.01 };
      })
      .toEqual({ layout: initialLayout, scaleChanged: true });
  }

  await page.getByTestId("marimo-plugin-slides-fullscreen").click();
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement !== null))
    .toBe(true);
  await expect
    .poll(async () => {
      const { scale, ...layout } = await measureLayout(deck);
      return layout;
    })
    .toEqual(initialLayout);

  await page.evaluate(() => document.exitFullscreen());
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement === null))
    .toBe(true);
  await expect
    .poll(async () => {
      const { scale, ...layout } = await measureLayout(deck);
      return layout;
    })
    .toEqual(initialLayout);

  await deck
    .getByRole("slider", { name: "Parameter", exact: true })
    .press("ArrowRight");
  await expect(
    deck.getByRole("slider", { name: "Parameter", exact: true }),
  ).toHaveAttribute("aria-valuenow", "6");
  await expect(
    deck.getByTestId("slide-scroll-container").getByText("Parameter value:"),
  ).toHaveText("Parameter value: 6");
});
