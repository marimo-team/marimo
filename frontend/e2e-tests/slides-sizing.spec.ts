/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test, type Locator } from "@playwright/test";
import { copyFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { getAppUrl } from "../playwright.config";
import { openCommandPalette, pressShortcut } from "./helper";

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

test.beforeEach(async ({ page }, testInfo) => {
  const notebook = testInfo.outputPath(`slides_sizing_${Date.now()}.py`);
  const layoutDirectory = testInfo.outputPath("layouts");
  await mkdir(layoutDirectory, { recursive: true });
  await copyFile(new URL("./py/slides_sizing.py", import.meta.url), notebook);
  await copyFile(
    new URL("./py/layouts/slides_sizing.slides.json", import.meta.url),
    path.join(layoutDirectory, "slides_sizing.slides.json"),
  );
  const url = new URL(getAppUrl("slides_sizing.py"));
  url.searchParams.set("file", notebook);
  await page.goto(url.toString(), { waitUntil: "domcontentloaded" });
  await page
    .locator(".marimo-cell, [role='button'][data-cell-id]")
    .first()
    .waitFor();
  await openCommandPalette({ page, command: "Re-run all cells" });
  if (!(await page.locator(".reveal.mo-slides-theme").isVisible())) {
    await openCommandPalette({ page, command: "Present as Slides" });
  }
});

test("slides preserve layout when the viewport and fullscreen state change", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 1000 });

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
      const { scale: _scale, ...layout } = await measureLayout(deck);
      return layout;
    })
    .toEqual(initialLayout);

  await page.evaluate(() => document.exitFullscreen());
  await expect
    .poll(() => page.evaluate(() => document.fullscreenElement === null))
    .toBe(true);
  await expect
    .poll(async () => {
      const { scale: _scale, ...layout } = await measureLayout(deck);
      return layout;
    })
    .toEqual(initialLayout);

  const track = deck.getByTestId("track");
  const trackBounds = await track.boundingBox();
  if (!trackBounds) {
    throw new Error("Slider track is not visible");
  }
  await track.click({
    position: { x: trackBounds.width * 0.6, y: trackBounds.height / 2 },
  });
  await expect(
    deck.getByRole("slider", { name: "Parameter", exact: true }),
  ).toHaveAttribute("aria-valuenow", "6");
  await expect(
    deck.getByTestId("slide-scroll-container").getByText("Parameter value:"),
  ).toHaveText("Parameter value: 6");
});

test("scroll hint accounts for scaled unrevealed fragments", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 });

  const deck = page.locator(".reveal.mo-slides-theme");
  await deck.press("ArrowRight");
  const slide = deck.locator("section.present");
  await expect(
    slide.getByRole("heading", { name: "Overflow before a fragment" }),
  ).toBeVisible();
  await expect(slide.locator(".fragment:not(.visible)")).toHaveCount(1);
  await expect(slide.getByTestId("slide-scroll-hint")).toBeVisible();
  await slide.getByTestId("slide-scroll-container").evaluate((el) => {
    el.scrollTop = 100;
  });
  await expect(slide.getByTestId("slide-scroll-hint")).toHaveCount(0);
});

test("new cell output preserves its preview layout after navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  const thumbnails = page.locator("[role='button'][data-cell-id]");
  await thumbnails
    .nth(2)
    .getByRole("button", { name: "Add Python cell" })
    .click();
  await expect(thumbnails).toHaveCount(6);
  await thumbnails.nth(3).click();
  const editor = page.locator(".cm-content:visible");
  await expect(editor).toHaveCount(1);
  await editor.fill(
    'mo.md("New output keeps the same line breaks across preview and presentation. " * 20)',
  );
  await pressShortcut(page, "cell.run");
  await expect(
    page.getByText("New output keeps", { exact: false }).last(),
  ).toBeVisible();
  await expect(editor).toBeFocused();
  await page.getByRole("button", { name: "Hide code", exact: true }).click();

  const preview = page.getByTestId("slide-preview-canvas");
  await expect(preview).toBeVisible();
  const measure = (root: Locator) =>
    root
      .locator(".paragraph, p")
      .first()
      .evaluate((el) => ({
        width: el.clientWidth,
        height: el.clientHeight,
        screenWidth: el.getBoundingClientRect().width,
      }));
  const initialPreview = await measure(preview);
  await page.setViewportSize({ width: 800, height: 600 });
  await expect
    .poll(async () => {
      const current = await measure(preview);
      return {
        width: current.width,
        height: current.height,
        scaledDown: current.screenWidth < initialPreview.screenWidth,
      };
    })
    .toEqual({
      width: initialPreview.width,
      height: initialPreview.height,
      scaledDown: true,
    });
  const previewLayout = await measure(preview);
  const deck = page.locator(".reveal.mo-slides-theme").first();
  await deck.press("ArrowLeft");
  await expect(preview).toHaveCount(0);
  await deck.press("ArrowRight");
  await expect
    .poll(() => measure(deck.locator("section.present")))
    .toEqual(previewLayout);
});
