/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { visibleForTesting } from "../download-html";

const { updateAssetUrl } = visibleForTesting;

describe("updateAssetUrl", () => {
  const assetBaseUrl =
    "https://cdn.jsdelivr.net/npm/@marimo-team/frontend@0.1.43/dist";

  it('should convert relative URL starting with "./"', () => {
    const existingUrl = "./assets/index-c78b8d10.js";
    const expected = `${assetBaseUrl}/assets/index-c78b8d10.js`;
    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(expected);
  });

  it('should convert relative URL starting with "/"', () => {
    const existingUrl = "/assets/index-c78b8d10.js";
    const expected = `${assetBaseUrl}/assets/index-c78b8d10.js`;
    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(expected);
  });

  it("should convert absolute URL from a different origin", () => {
    const existingUrl = "https://localhost:8080/assets/index-c78b8d10.js";
    const expected = `${assetBaseUrl}/assets/index-c78b8d10.js`;
    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(expected);
  });

  it("should not modify URL from the same origin", () => {
    // Assuming window.location.origin is 'https://localhost:8080'
    const existingUrl = "https://localhost:8080/assets/index-c78b8d10.js";
    // Mock window.location.origin to match the existingUrl's origin
    Object.defineProperty(globalThis, "location", {
      value: {
        origin: "https://localhost:8080",
      },
    });

    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(existingUrl);
  });
});
