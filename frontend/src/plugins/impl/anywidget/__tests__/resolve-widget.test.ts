/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import {
  getInvalidAnyWidgetModuleError,
  isAnyWidgetModule,
  resolveAnyWidget,
} from "../resolve-widget";

describe("isAnyWidgetModule", () => {
  it("should accept a default object with render", () => {
    expect(isAnyWidgetModule({ default: { render: () => undefined } })).toBe(
      true,
    );
  });

  it("should accept a default factory function", () => {
    expect(
      isAnyWidgetModule({ default: async () => ({ render: () => {} }) }),
    ).toBe(true);
  });

  it("should reject legacy named render exports", () => {
    expect(isAnyWidgetModule({ render: () => undefined })).toBe(false);
  });
});

describe("resolveAnyWidget", () => {
  const jsUrl = "./@file/widget.js";

  it("should return the default export when present", () => {
    const widget = { render: () => undefined };
    expect(resolveAnyWidget({ default: widget }, jsUrl)).toBe(widget);
  });

  it("should return a default factory function", () => {
    const factory = async () => ({ render: () => {} });
    expect(resolveAnyWidget({ default: factory }, jsUrl)).toBe(factory);
  });

  it("should synthesize a widget from a legacy named render export", () => {
    const render = vi.fn();
    const resolved = resolveAnyWidget({ render }, jsUrl);
    expect(resolved).not.toBeNull();
    expect(resolved).toMatchObject({ render });
  });

  it("should synthesize a widget from a legacy named initialize export", () => {
    const initialize = vi.fn();
    const resolved = resolveAnyWidget({ initialize }, jsUrl);
    expect(resolved).not.toBeNull();
    expect(resolved).toMatchObject({ initialize });
  });

  it("should return null for a module with no valid exports", () => {
    expect(resolveAnyWidget({}, jsUrl)).toBeNull();
    expect(resolveAnyWidget({ default: {} }, jsUrl)).toBeNull();
    expect(resolveAnyWidget({ render: "not a function" }, jsUrl)).toBeNull();
  });

  it("should return a stable widget identity across calls for one module", () => {
    const mod = { render: vi.fn() };
    expect(resolveAnyWidget(mod, jsUrl)).toBe(resolveAnyWidget(mod, jsUrl));
  });

  it("should not fall back to named exports when a default export is present", () => {
    // A present-but-invalid default should surface an error, not be masked.
    expect(
      resolveAnyWidget({ default: {}, render: vi.fn() }, jsUrl),
    ).toBeNull();
  });
});

describe("getInvalidAnyWidgetModuleError", () => {
  const jsUrl = "./@file/widget.js";

  it("should explain legacy named render exports", () => {
    const error = getInvalidAnyWidgetModuleError(
      { render: () => undefined },
      jsUrl,
    );
    expect(error.message).toContain("named exports (`render`)");
    expect(error.message).toContain("`export default { render }`");
    expect(error.message).toContain("not `export function render`");
  });

  it("should explain legacy named initialize exports", () => {
    const error = getInvalidAnyWidgetModuleError(
      { initialize: () => undefined },
      jsUrl,
    );
    expect(error.message).toContain("named exports (`initialize`)");
    expect(error.message).toContain("`export default { initialize }`");
    expect(error.message).toContain("not `export function initialize`");
  });

  it("should avoid nested backticks for multi-hook named exports", () => {
    const error = getInvalidAnyWidgetModuleError(
      { render: () => undefined, initialize: () => undefined },
      jsUrl,
    );
    expect(error.message).toContain(
      "`export default { render, initialize }` (not `named export function ...`).",
    );
    expect(error.message).not.toContain("`named `export");
  });

  it("should explain a missing default export", () => {
    expect(getInvalidAnyWidgetModuleError({}, jsUrl).message).toContain(
      "missing a default export",
    );
    expect(getInvalidAnyWidgetModuleError(null, jsUrl).message).toContain(
      "missing a default export",
    );
  });

  it("should explain an invalid default export", () => {
    const error = getInvalidAnyWidgetModuleError({ default: {} }, jsUrl);
    expect(error.message).toContain("invalid default export");
    expect(error.message).toContain("https://anywidget.dev/en/afm/");
  });
});
