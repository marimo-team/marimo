/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseWidgetRef, WIDGET_REF_PREFIX } from "../widget-ref";

describe("parseWidgetRef", () => {
  it("parses an anywidget: ref", () => {
    expect(parseWidgetRef(`${WIDGET_REF_PREFIX}abc-123`)).toBe("abc-123");
  });

  it("rejects the legacy IPY_MODEL_ prefix", () => {
    expect(() => parseWidgetRef("IPY_MODEL_abc-123")).toThrow(/Invalid/);
  });

  it("rejects a bare model id", () => {
    expect(() => parseWidgetRef("abc-123")).toThrow(/Invalid/);
  });

  it("rejects non-string inputs", () => {
    expect(() => parseWidgetRef(undefined)).toThrow(/Invalid/);
    expect(() => parseWidgetRef(null)).toThrow(/Invalid/);
    expect(() => parseWidgetRef(42)).toThrow(/Invalid/);
    expect(() => parseWidgetRef({ model_id: "abc" })).toThrow(/Invalid/);
  });
});
