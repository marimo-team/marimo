/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  EDGE_CASE_FILENAMES,
  URL_SPECIAL_CHAR_FILENAMES,
} from "../../__tests__/mocks";
import { appendQueryParams, isUrl, updateQueryParams } from "../urls";

describe("isUrl", () => {
  it("should return true for a valid URL", () => {
    expect(isUrl("https://example.com")).toBe(true);
    expect(isUrl("curl -X GET http://example.com")).toBe(false);
  });
});

describe("URL parameter handling with edge case filenames", () => {
  it.each(
    EDGE_CASE_FILENAMES,
  )("should handle unicode filenames in URL parameters: %s", (filename) => {
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
  });

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

describe("appendQueryParams", () => {
  it("should append params to a simple path", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: new URLSearchParams("file=test.py"),
    });
    expect(result).toBe("/about?file=test.py");
  });

  it("should append params to a hash-based path", () => {
    const result = appendQueryParams({
      href: "#/about",
      queryParams: new URLSearchParams("file=test.py"),
    });
    expect(result).toBe("/?file=test.py#/about");
  });

  it("should accept query string instead of URLSearchParams", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: "file=test.py&mode=edit",
    });
    expect(result).toBe("/about?file=test.py&mode=edit");
  });

  it("should filter params by keys when provided", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: "file=test.py&mode=edit&extra=data",
      keys: ["file", "mode"],
    });
    expect(result).toBe("/about?file=test.py&mode=edit");
  });

  it("should filter params by keys in the middle of the query string", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: "file=test.py&mode=edit&extra=data",
      keys: ["file", "extra"],
    });
    expect(result).toBe("/about?file=test.py&extra=data");
  });

  it("should preserve existing query params", () => {
    const result = appendQueryParams({
      href: "/about?existing=1",
      queryParams: "file=test.py",
    });
    expect(result).toBe("/about?existing=1&file=test.py");
  });

  it("should overwrite existing params with same key", () => {
    const result = appendQueryParams({
      href: "/about?file=old.py",
      queryParams: "file=new.py",
    });
    expect(result).toBe("/about?file=new.py");
  });

  it("should preserve hash fragment and put params before it", () => {
    const result = appendQueryParams({
      href: "/about#section",
      queryParams: "file=test.py",
    });
    expect(result).toBe("/about?file=test.py#section");
  });

  it("should handle hash-based path with existing params and hash", () => {
    const result = appendQueryParams({
      href: "#/about?existing=1",
      queryParams: "file=test.py",
    });
    expect(result).toBe("#/about?existing=1&file=test.py");
  });

  it("should handle hash-based path", () => {
    const result = appendQueryParams({
      href: "#/about",
      queryParams: "file=test.py",
    });
    expect(result).toBe("/?file=test.py#/about");
  });

  it("should not modify external links", () => {
    const httpUrl = "http://example.com/page";
    const httpsUrl = "https://example.com/page";

    expect(
      appendQueryParams({
        href: httpUrl,
        queryParams: "file=test.py",
      }),
    ).toBe(httpUrl);

    expect(
      appendQueryParams({
        href: httpsUrl,
        queryParams: "file=test.py",
      }),
    ).toBe(httpsUrl);
  });

  it("should return original href when no params to append", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: new URLSearchParams(),
    });
    expect(result).toBe("/about");
  });

  it("should handle complex scenarios with all features", () => {
    const result = appendQueryParams({
      href: "#/dashboard?view=grid#top",
      queryParams: "file=notebook.py&view=list&mode=edit",
      keys: ["file", "mode"],
    });
    // view=grid should remain, file and mode should be added (view is not in keys)
    expect(result).toBe("#/dashboard?view=grid&file=notebook.py&mode=edit#top");
  });

  it("should handle empty path", () => {
    const result = appendQueryParams({
      href: "",
      queryParams: "file=test.py",
    });
    expect(result).toBe("?file=test.py");
  });

  it("should handle just a hash", () => {
    const result = appendQueryParams({
      href: "#",
      queryParams: "file=test.py",
    });
    expect(result).toBe("/?file=test.py#");
  });

  it("should handle unicode filenames in params", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: new URLSearchParams([
        ["file", "文件.py"],
        ["name", "テスト"],
      ]),
    });
    expect(result).toContain("/about?");
    // Verify the params are properly encoded
    const url = new URL(result, "http://example.com");
    expect(url.searchParams.get("file")).toBe("文件.py");
    expect(url.searchParams.get("name")).toBe("テスト");
  });

  it("should handle special characters in param values", () => {
    const result = appendQueryParams({
      href: "/about",
      queryParams: new URLSearchParams([
        ["path", "folder/file with spaces.py"],
      ]),
    });
    expect(result).toContain("/about?");
    const url = new URL(result, "http://example.com");
    expect(url.searchParams.get("path")).toBe("folder/file with spaces.py");
  });
});
