/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  EDGE_CASE_FILENAMES,
  URL_SPECIAL_CHAR_FILENAMES,
} from "../../__tests__/mocks";
import { isUrl, updateQueryParams } from "../urls";

describe("isUrl", () => {
  it("should return true for a valid URL", () => {
    expect(isUrl("https://example.com")).toBe(true);
    expect(isUrl("curl -X GET http://example.com")).toBe(false);
  });
});

describe("URL parameter handling with edge case filenames", () => {
  it.each(EDGE_CASE_FILENAMES)(
    "should handle unicode filenames in URL parameters: %s",
    (filename) => {
      // Test that updateQueryParams can handle unicode filenames
      updateQueryParams((params) => {
        params.set("file", filename);
      });

      // Verify URL encoding/decoding works with unicode
      const encoded = encodeURIComponent(filename);
      const decoded = decodeURIComponent(encoded);
      expect(decoded).toBe(filename);

      // Verify filename can be safely added to URL parameters
      const url = new URL("https://example.com");
      url.searchParams.set("file", filename);
      expect(url.searchParams.get("file")).toBe(filename);
    },
  );

  it("should preserve unicode in query string round-trip", () => {
    EDGE_CASE_FILENAMES.forEach((filename) => {
      const url = new URL("https://example.com");
      url.searchParams.set("filename", filename);

      // Convert to string and back
      const urlString = url.toString();
      const reconstructed = new URL(urlString);
      const retrievedFilename = reconstructed.searchParams.get("filename");

      expect(retrievedFilename).toBe(filename);
    });
  });

  it("should handle special characters in updateQueryParams", () => {
    URL_SPECIAL_CHAR_FILENAMES.forEach((filename) => {
      let res: string | null = null;
      expect(() => {
        updateQueryParams((params) => {
          // To and from conversion
          params.set("file", filename);
          res = params.get("file");
        });
      }).not.toThrow();
      expect(res).not.toBeNull();
      expect(res).toBe(filename);
    });
  });
});
