/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "@playwright/test";
import { getAppUrl } from "../playwright.config";
import { waitForMarimoApp } from "./test-utils";

const apps = ["visual_tokens.py", "visual_tokens.py//run"] as const;

test("semantic token fixture loads in edit and read views", async ({
  browser,
}) => {
  for (const app of apps) {
    const page = await browser.newPage();
    await page.goto(getAppUrl(app));
    await waitForMarimoApp(page);
    await expect(
      page.getByRole("heading", { name: "Semantic token fixture" }),
    ).toBeVisible();
    await page.close();
  }
});
