/* Copyright 2024 Marimo. All rights reserved. */
import { beforeAll, describe, expect, test } from "vitest";
import { asURL } from "../url";

describe("asURL function", () => {
  describe("when document.baseURI is not set", () => {
    // Mock document.baseURI
    beforeAll(() => {
      Object.defineProperty(document, "baseURI", {
        value: "https://example.com/",
        writable: true,
      });
    });

    test('should handle relative path starting with "./"', () => {
      const path = "./path/to/resource";
      const result = asURL(path);
      expect(result.toString()).toBe("https://example.com/path/to/resource");
    });

    test('should handle absolute path starting with "/"', () => {
      const path = "/path/to/resource";
      const result = asURL(path);
      expect(result.toString()).toBe("https://example.com/path/to/resource");
    });

    test("should handle full URL", () => {
      const fullPath = "https://example.com/path/to/resource";
      const result = asURL(fullPath);
      expect(result.toString()).toBe(fullPath);
    });

    test('should handle relative path without "./"', () => {
      const path = "path/to/resource";
      const result = asURL(path);
      expect(result.toString()).toBe("https://example.com/path/to/resource");
    });

    test("relative with query params", () => {
      const path = "path/to/resource?query=param";
      const result = asURL(path);
      expect(result.toString()).toBe(
        "https://example.com/path/to/resource?query=param",
      );
    });

    test("just query params", () => {
      const path = "?query=param";
      const result = asURL(path);
      expect(result.toString()).toBe("https://example.com/?query=param");
    });
  });

  describe("when document.baseURI is set", () => {
    // Mock document.baseURI
    beforeAll(() => {
      Object.defineProperty(document, "baseURI", {
        value: "https://example.com/base/",
        writable: true,
      });
    });

    test('should handle relative path starting with "./"', () => {
      const result = asURL("./path/to/resource");
      expect(result.toString()).toBe(
        "https://example.com/base/path/to/resource",
      );
    });

    test('should handle absolute path starting with "/"', () => {
      const result = asURL("/path/to/resource");
      expect(result.toString()).toBe("https://example.com/path/to/resource");
    });

    test("should handle full URL", () => {
      const fullPath = "https://example.com/path/to/resource";
      const result = asURL(fullPath);
      expect(result.toString()).toBe(fullPath);
    });

    test('should handle relative path without "./"', () => {
      const result = asURL("path/to/resource");
      expect(result.toString()).toBe(
        "https://example.com/base/path/to/resource",
      );
    });

    test("relative with query params", () => {
      const result = asURL("path/to/resource?query=param");
      expect(result.toString()).toBe(
        "https://example.com/base/path/to/resource?query=param",
      );
    });

    test("just query params", () => {
      const result = asURL("?query=param");
      expect(result.toString()).toBe("https://example.com/base/?query=param");
    });
  });
});
