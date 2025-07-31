/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable no-console */

import { chromium, type FullConfig } from "@playwright/test";
import { type ApplicationNames, getAppUrl } from "../playwright.config";

async function globalSetup(config: FullConfig) {
  // Start a browser to test server connectivity
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Test some apps to ensure they're ready
  const criticalApps: ApplicationNames[] = ["components.py"];

  console.log("🔧 Testing server connectivity...");

  for (const app of criticalApps) {
    try {
      const url = getAppUrl(app);
      console.log(`Testing ${app} at ${url}`);

      // Wait for server to be ready with retries
      let retries = 3;
      while (retries > 0) {
        try {
          await page.goto(url, {
            waitUntil: "networkidle",
            timeout: 15_000,
          });
          console.log(`✅ ${app} ready`);
          break;
        } catch (error) {
          retries--;
          if (retries === 0) {
            console.error(`❌ ${app} failed to start:`, error);
            throw error;
          }
          console.log(`⏳ Retrying ${app} (${retries} attempts left)`);
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      }
    } catch (error) {
      console.error(`Failed to connect to ${app}:`, error);
      throw error;
    }
  }

  await browser.close();
  console.log("🎉 All servers ready!");
}

export default globalSetup;
