/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import type { MimeType } from "@/components/editor/Output";
import {
  applyHidingRules,
  createMimeConfig,
  getDefaultMimeConfig,
  processMimeBundle,
  sortByPrecedence,
} from "../mime-types";

/** Helper to build a hiding rules Map inline */
function hidingRules(
  rules: Record<string, MimeType[]>,
): ReadonlyMap<MimeType, ReadonlySet<MimeType>> {
  const map = new Map<MimeType, ReadonlySet<MimeType>>();
  for (const [trigger, toHide] of Object.entries(rules)) {
    map.set(trigger as MimeType, new Set(toHide));
  }
  return map;
}

/** Helper to build a precedence Map inline */
function precedenceMap(types: MimeType[]): ReadonlyMap<MimeType, number> {
  const map = new Map<MimeType, number>();
  types.forEach((mime, i) => map.set(mime, i));
  return map;
}

describe("mime-types", () => {
  describe("applyHidingRules", () => {
    it("should return all visible when no rules match", () => {
      const mimeTypes = new Set<MimeType>(["text/plain", "text/markdown"]);
      const rules = hidingRules({ "text/html": ["image/png"] });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.visible).toEqual(new Set(["text/plain", "text/markdown"]));
      expect(result.hidden.size).toBe(0);
    });

    it("should hide mime types when trigger is present", () => {
      const mimeTypes = new Set<MimeType>([
        "text/html",
        "image/png",
        "text/plain",
      ]);
      const rules = hidingRules({ "text/html": ["image/png"] });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.visible).toEqual(new Set(["text/html", "text/plain"]));
      expect(result.hidden).toEqual(new Set(["image/png"]));
    });

    it("should not hide markdown when html is present (per requirements)", () => {
      const mimeTypes = new Set<MimeType>([
        "text/html",
        "text/markdown",
        "image/png",
      ]);
      const rules = hidingRules({ "text/html": ["image/png"] });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.visible.has("text/markdown")).toBe(true);
      expect(result.visible.has("text/html")).toBe(true);
      expect(result.hidden.has("image/png")).toBe(true);
    });

    it("should handle multiple matching rules", () => {
      const mimeTypes = new Set<MimeType>([
        "text/html",
        "application/vnd.vegalite.v5+json",
        "image/png",
        "image/jpeg",
      ]);
      const rules = hidingRules({
        "text/html": ["image/png"],
        "application/vnd.vegalite.v5+json": ["image/jpeg"],
      });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.hidden).toEqual(new Set(["image/png", "image/jpeg"]));
      expect(result.visible).toEqual(
        new Set(["text/html", "application/vnd.vegalite.v5+json"]),
      );
    });

    it("should handle empty mime types", () => {
      const mimeTypes = new Set<MimeType>();
      const rules = hidingRules({ "text/html": ["image/png"] });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.visible.size).toBe(0);
      expect(result.hidden.size).toBe(0);
    });

    it("should handle empty rules", () => {
      const mimeTypes = new Set<MimeType>(["text/html", "image/png"]);
      const rules = hidingRules({});

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.visible).toEqual(mimeTypes);
      expect(result.hidden.size).toBe(0);
    });

    it("should hide a type that is also a trigger if configured", () => {
      const mimeTypes = new Set<MimeType>(["text/html", "text/plain"]);
      const rules = hidingRules({ "text/html": ["text/html"] });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.hidden.has("text/html")).toBe(true);
    });

    it("should not hide types that are not present", () => {
      const mimeTypes = new Set<MimeType>(["text/html"]);
      const rules = hidingRules({
        "text/html": ["image/png", "image/jpeg"],
      });

      const result = applyHidingRules(mimeTypes, rules);

      expect(result.hidden.size).toBe(0);
      expect(result.visible).toEqual(new Set(["text/html"]));
    });
  });

  describe("sortByPrecedence", () => {
    it("should sort entries by precedence order", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/plain", "plain"],
        ["text/html", "html"],
        ["image/png", "png"],
      ];

      const result = sortByPrecedence(
        entries,
        precedenceMap(["text/html", "image/png", "text/plain"]),
      );

      expect(result.map(([m]) => m)).toEqual([
        "text/html",
        "image/png",
        "text/plain",
      ]);
    });

    it("should place unknown mime types at the end", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/plain", "plain"],
        ["text/html", "html"],
        ["application/json", "json"],
      ];

      const result = sortByPrecedence(entries, precedenceMap(["text/html"]));

      expect(result[0][0]).toBe("text/html");
      expect(result.slice(1).map(([m]) => m)).toEqual([
        "text/plain",
        "application/json",
      ]);
    });

    it("should handle empty entries", () => {
      const result = sortByPrecedence([], precedenceMap(["text/html"]));

      expect(result).toEqual([]);
    });

    it("should handle empty precedence", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/plain", "plain"],
        ["text/html", "html"],
      ];

      const result = sortByPrecedence(entries, precedenceMap([]));

      expect(result.map(([m]) => m)).toEqual(["text/plain", "text/html"]);
    });

    it("should not mutate original array", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/plain", "plain"],
        ["text/html", "html"],
      ];
      const original = [...entries];

      sortByPrecedence(entries, precedenceMap(["text/html", "text/plain"]));

      expect(entries).toEqual(original);
    });
  });

  describe("processMimeBundle", () => {
    it("should filter and sort mime entries", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/plain", "plain"],
        ["text/html", "html"],
        ["image/png", "png"],
      ];

      const config = createMimeConfig({
        precedence: ["text/html", "text/plain"],
        hidingRules: { "text/html": ["image/png"] },
      });

      const result = processMimeBundle(entries, config);

      expect(result.entries.map(([m]) => m)).toEqual([
        "text/html",
        "text/plain",
      ]);
      expect(result.hidden).toEqual(["image/png"]);
    });

    it("should handle empty entries", () => {
      const result = processMimeBundle([]);

      expect(result.entries).toEqual([]);
      expect(result.hidden).toEqual([]);
    });

    it("should use default config when not provided", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/html", "html"],
        ["image/png", "png"],
        ["text/markdown", "md"],
      ];

      const result = processMimeBundle(entries);

      expect(result.entries.map(([m]) => m)).not.toContain("image/png");
      expect(result.entries.map(([m]) => m)).toContain("text/markdown");
    });

    it("should preserve data associated with mime types", () => {
      const htmlData = { content: "<h1>Hello</h1>" };
      const entries: Array<[MimeType, typeof htmlData]> = [
        ["text/html", htmlData],
      ];

      const result = processMimeBundle(entries);

      expect(result.entries[0][1]).toBe(htmlData);
    });

    it("should sort by precedence after filtering", () => {
      const entries: Array<[MimeType, string]> = [
        ["text/plain", "plain"],
        ["text/markdown", "md"],
        ["text/html", "html"],
      ];

      const result = processMimeBundle(entries);

      expect(result.entries[0][0]).toBe("text/html");
    });
  });

  describe("getDefaultMimeConfig", () => {
    const config = getDefaultMimeConfig();

    it("should have text/html as highest precedence", () => {
      expect(config.precedence.get("text/html")).toBe(0);
    });

    it("should hide image types when html is present", () => {
      const htmlHides = config.hidingRules.get("text/html");

      expect(htmlHides).toBeDefined();
      expect(htmlHides?.has("image/png")).toBe(true);
      expect(htmlHides?.has("image/jpeg")).toBe(true);
    });

    it("should NOT hide markdown when html is present", () => {
      const htmlHides = config.hidingRules.get("text/html");

      expect(htmlHides?.has("text/markdown")).toBeFalsy();
    });

    it("should hide images when vega charts are present", () => {
      const vegaHides = config.hidingRules.get(
        "application/vnd.vegalite.v5+json",
      );

      expect(vegaHides).toBeDefined();
      expect(vegaHides?.has("image/png")).toBe(true);
    });

    it("should return the same instance on repeated calls", () => {
      expect(getDefaultMimeConfig()).toBe(config);
    });
  });

  describe("createMimeConfig", () => {
    it("should compile precedence array into a Map", () => {
      const config = createMimeConfig({
        precedence: ["text/html", "image/png"],
        hidingRules: {},
      });

      expect(config.precedence.get("text/html")).toBe(0);
      expect(config.precedence.get("image/png")).toBe(1);
      expect(config.precedence.has("text/plain")).toBe(false);
    });

    it("should compile hiding rules into Map<MimeType, Set>", () => {
      const config = createMimeConfig({
        precedence: [],
        hidingRules: {
          "text/html": ["image/png", "image/jpeg"],
        },
      });

      const htmlHides = config.hidingRules.get("text/html");
      expect(htmlHides).toBeInstanceOf(Set);
      expect(htmlHides?.has("image/png")).toBe(true);
      expect(htmlHides?.has("image/jpeg")).toBe(true);
    });
  });
});
