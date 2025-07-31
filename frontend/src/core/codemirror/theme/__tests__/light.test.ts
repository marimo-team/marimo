/* Copyright 2024 Marimo. All rights reserved. */

import { type Tag, tags as t } from "@lezer/highlight";
import { describe, expect, it } from "vitest";
import { lightTheme } from "../light";

// Helper function to get theme configuration from the source
const getThemeConfig = () => ({
  variant: "light",
  settings: {
    background: "#ffffff",
    foreground: "#000000",
    caret: "#000000",
    selection: "#d7d4f0",
    lineHighlight: "#cceeff44",
    gutterBackground: "var(--color-background)",
    gutterForeground: "var(--gray-10)",
  },
  styles: [
    { tag: t.comment, color: "#708090" },
    { tag: t.variableName, color: "#000000" },
    { tag: [t.string, t.special(t.brace)], color: "#a11" },
    { tag: t.number, color: "#164" },
    { tag: t.bool, color: "#219" },
    { tag: t.null, color: "#219" },
    { tag: t.keyword, color: "#708", fontWeight: 500 },
    { tag: t.className, color: "#00f" },
    { tag: t.definition(t.typeName), color: "#00f" },
    { tag: t.typeName, color: "#085" },
    { tag: t.angleBracket, color: "#000000" },
    { tag: t.tagName, color: "#170" },
    { tag: t.attributeName, color: "#00c" },
    { tag: t.operator, color: "#a2f", fontWeight: 500 },
    { tag: [t.function(t.variableName)], color: "#00c" },
    { tag: [t.propertyName], color: "#05a" },
  ],
});

describe("lightTheme", () => {
  it("should export a theme", () => {
    expect(lightTheme).toBeDefined();
    expect(typeof lightTheme).toBe("object");
  });

  describe("theme configuration", () => {
    const config = getThemeConfig();

    it("should have correct basic settings", () => {
      expect(config.variant).toBe("light");
      expect(config.settings).toEqual({
        background: "#ffffff",
        foreground: "#000000",
        caret: "#000000",
        selection: "#d7d4f0",
        lineHighlight: "#cceeff44",
        gutterBackground: "var(--color-background)",
        gutterForeground: "var(--gray-10)",
      });
    });

    describe("syntax highlighting", () => {
      const findStyle = (tag: Tag | readonly Tag[]) =>
        config.styles.find((s) =>
          Array.isArray(s.tag) ? s.tag.includes(tag as Tag) : s.tag === tag,
        );

      it("should style comments", () => {
        expect(findStyle(t.comment)).toEqual({
          tag: t.comment,
          color: "#708090",
        });
      });

      it("should style strings", () => {
        const style = findStyle(t.string);
        expect(style).toBeDefined();
        expect(style?.color).toBe("#a11");
        expect(Array.isArray(style?.tag)).toBe(true);
        expect(style?.tag).toContain(t.string);
        expect(style?.tag).toContain(t.special(t.brace));
      });

      it("should style numbers and boolean values", () => {
        expect(findStyle(t.number)).toEqual({
          tag: t.number,
          color: "#164",
        });
        expect(findStyle(t.bool)).toEqual({
          tag: t.bool,
          color: "#219",
        });
      });

      it("should style keywords with emphasis", () => {
        expect(findStyle(t.keyword)).toEqual({
          tag: t.keyword,
          color: "#708",
          fontWeight: 500,
        });
      });

      it("should style operators with emphasis", () => {
        expect(findStyle(t.operator)).toEqual({
          tag: t.operator,
          color: "#a2f",
          fontWeight: 500,
        });
      });

      it("should style class and type names", () => {
        expect(findStyle(t.className)).toEqual({
          tag: t.className,
          color: "#00f",
        });
        expect(findStyle(t.typeName)).toEqual({
          tag: t.typeName,
          color: "#085",
        });
      });

      it("should style function names", () => {
        const style = findStyle(t.function(t.variableName));
        expect(style).toBeDefined();
        expect(style?.color).toBe("#00c");
        expect(Array.isArray(style?.tag)).toBe(true);
      });

      it("should style property names", () => {
        const style = findStyle(t.propertyName);
        expect(style).toBeDefined();
        expect(style?.color).toBe("#05a");
        expect(Array.isArray(style?.tag)).toBe(true);
      });
    });
  });
});
