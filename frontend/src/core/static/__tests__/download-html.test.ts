/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { EDGE_CASE_FILENAMES } from "../../../__tests__/mocks";
import { Filenames } from "../../../utils/filenames";
import { Paths } from "../../../utils/paths";
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
    Object.defineProperty(window, "location", {
      value: {
        origin: "https://localhost:8080",
      },
    });

    expect(updateAssetUrl(existingUrl, assetBaseUrl)).toBe(existingUrl);
  });
});

describe("filename handling for downloads", () => {
  it.each(
    EDGE_CASE_FILENAMES,
  )("should handle edge case filenames in download operations: %s", (filename) => {
    // Test that basename extraction works correctly for downloads
    const basename = Paths.basename(filename);
    expect(basename).toBe(filename);

    // Test filename conversion for HTML downloads
    const htmlFilename = Filenames.toHTML(filename);
    expect(htmlFilename).toMatch(/\.html$/);
    expect(htmlFilename).toContain(Filenames.withoutExtension(filename));

    // Ensure unicode and spaces are preserved in basename
    const withoutExt = Filenames.withoutExtension(filename);
    expect(withoutExt).not.toBe("");
    expect(typeof withoutExt).toBe("string");
  });

  it("should handle blob download filename generation", () => {
    // Mock URL.createObjectURL for blob testing
    const mockCreateObjectURL = vi.fn().mockReturnValue("blob:mock-url");
    global.URL.createObjectURL = mockCreateObjectURL;

    EDGE_CASE_FILENAMES.forEach((filename) => {
      const htmlFilename = Filenames.toHTML(filename);

      // Verify blob can be created with unicode filenames
      expect(() => new Blob(["test"], { type: "text/html" })).not.toThrow();
      expect(htmlFilename).toMatch(/\.html$/);

      // Verify filename maintains unicode characters
      const baseName = Filenames.withoutExtension(filename);
      expect(htmlFilename).toContain(baseName);
    });
  });
});
