/* Copyright 2024 Marimo. All rights reserved. */
import { beforeAll, expect, describe, test } from "vitest";
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
      expect(result.toString()).toBe(
        "https://example.com/base/path/to/resource",
      );
    });
  });
});
