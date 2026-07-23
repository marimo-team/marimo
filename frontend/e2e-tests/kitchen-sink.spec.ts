/* Copyright 2026 Marimo. All rights reserved. */

import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import {
  exportAsHTMLAndTakeScreenshot,
  exportAsPNG,
  takeScreenshot,
} from "./helper";

const _filename = fileURLToPath(import.meta.url);

const appUrl = getAppUrl("kitchen_sink.py");

test("can screenshot and download as html", async ({ page }) => {
  await page.goto(appUrl);

  await takeScreenshot(page, _filename);
  await exportAsHTMLAndTakeScreenshot(page);
});

test.skip("can screenshot and download as png", async ({ page }) => {
  await page.goto(appUrl);

  await exportAsPNG(page);
});

test("nav menu dropdown is not clipped by the cell output area", async ({
  page,
}) => {
  await page.goto(appUrl);

  const trigger = page.getByRole("button", { name: "Links" }).first();
  await trigger.scrollIntoViewIfNeeded();
  await trigger.hover();

  const link = page.getByRole("link", { name: "GitHub" }).first();
  await expect(link).toBeVisible();
  // The dropdown is portaled out of the cell's overflow container; a trial
  // click performs Playwright's hit-target check, which fails if the link is
  // clipped or covered by the cell output area, without navigating away.
  await link.click({ trial: true });
});
