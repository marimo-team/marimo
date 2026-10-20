/* Copyright 2026 Marimo. All rights reserved. */

import { chromium, type FullConfig } from "@playwright/test";
import { type ApplicationNames, getAppUrl } from "../playwright.config";
import { Logger } from "../src/utils/Logger";

async function globalSetup(_config: FullConfig) {
  // Start a browser to test server connectivity
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Test some apps to ensure they're ready
  const criticalApps: ApplicationNames[] = ["components.py"];

  Logger.log("🔧 Testing server connectivity...");

  for (const app of criticalApps) {
    try {
      const url = getAppUrl(app);
      Logger.log(`Testing ${app} at ${url}`);

      // Wait for server to be ready with retries
      let retries = 3;
      while (retries > 0) {
        try {
          await page.goto(url, {
            waitUntil: "load",
            timeout: 15_000,
          });
          Logger.log(`✅ ${app} ready`);
          break;
        } catch (error) {
          retries--;
          if (retries === 0) {
            Logger.error(`❌ ${app} failed to start:`, error);
            throw error;
          }
          Logger.log(`⏳ Retrying ${app} (${retries} attempts left)`);
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      }
    } catch (error) {
      Logger.error(`Failed to connect to ${app}:`, error);
      throw error;
    }
  }

  await browser.close();
  Logger.log("🎉 All servers ready!");
}

export default globalSetup;
