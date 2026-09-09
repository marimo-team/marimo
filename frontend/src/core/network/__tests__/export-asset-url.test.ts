/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { withDevAssetUrl } from "../export-asset-url";
import type { ExportAsHTMLRequest } from "../types";

const REQUEST: ExportAsHTMLRequest = {
  download: false,
  includeCode: true,
  files: [],
};

describe("withDevAssetUrl", () => {
  const originalEnv = process.env.NODE_ENV;

  afterEach(() => {
    process.env.NODE_ENV = originalEnv;
  });

  it.each(["development", "test"])(
    "defaults assetUrl to the dev server in %s",
    (env) => {
      process.env.NODE_ENV = env;
      expect(withDevAssetUrl(REQUEST).assetUrl).toBe(window.location.origin);
    },
  );

  it("leaves a caller-provided assetUrl alone in dev", () => {
    process.env.NODE_ENV = "development";
    const cdn = "https://cdn.example.com/dist";
    expect(withDevAssetUrl({ ...REQUEST, assetUrl: cdn }).assetUrl).toBe(cdn);
  });

  it("does nothing in production", () => {
    process.env.NODE_ENV = "production";
    expect(withDevAssetUrl(REQUEST)).toBe(REQUEST);
  });

  it("does not mutate the caller's request", () => {
    process.env.NODE_ENV = "development";
    const request = { ...REQUEST };
    withDevAssetUrl(request);
    expect(request.assetUrl).toBeUndefined();
  });
});
