/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";

const appUrl = getAppUrl("nav_menu.py");

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
