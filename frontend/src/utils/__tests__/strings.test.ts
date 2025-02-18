/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { Strings, decodeUtf8 } from "../strings";

describe("Strings", () => {
  describe("startCase", () => {
    it("handles empty string", () => {
      expect(Strings.startCase("")).toBe("");
    });

    it("handles non-letter strings", () => {
      expect(Strings.startCase("123")).toBe("123");
      expect(Strings.startCase("!@#")).toBe("!@#");
    });

    it("converts strings to start case", () => {
      expect(Strings.startCase("hello world")).toBe("Hello World");
      expect(Strings.startCase("camelCase")).toBe("Camel Case");
      expect(Strings.startCase("snake_case")).toBe("Snake Case");
    });

    it("throws for non-string input", () => {
      expect(() => Strings.startCase(123 as unknown as string)).toThrow();
    });
  });

  describe("htmlEscape", () => {
    it("handles undefined", () => {
      expect(Strings.htmlEscape(undefined)).toBeUndefined();
    });

    it("handles empty string", () => {
      expect(Strings.htmlEscape("")).toBe("");
    });

    it("escapes HTML special characters", () => {
      expect(Strings.htmlEscape("< > & \" ' \n")).toBe(
        "&lt; &gt; &amp; &quot; &#039;  ",
      );
      expect(Strings.htmlEscape("<script>alert('xss')</script>")).toBe(
        "&lt;script&gt;alert(&#039;xss&#039;)&lt;/script&gt;",
      );
    });
  });

  describe("withoutTrailingSlash", () => {
    it("removes trailing slash", () => {
      expect(Strings.withoutTrailingSlash("/path/")).toBe("/path");
      expect(Strings.withoutTrailingSlash("/path")).toBe("/path");
    });
  });

  describe("withoutLeadingSlash", () => {
    it("removes leading slash", () => {
      expect(Strings.withoutLeadingSlash("/path")).toBe("path");
      expect(Strings.withoutLeadingSlash("path")).toBe("path");
    });
  });
});

describe("decodeUtf8", () => {
  it("decodes UTF-8 array to string", () => {
    const encoder = new TextEncoder();
    const text = "Hello 世界";
    const encoded = encoder.encode(text);
    expect(decodeUtf8(encoded)).toBe(text);
  });
});
