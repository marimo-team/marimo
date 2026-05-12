/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { computeRenderPolicy } from "../render-policy";

describe("computeRenderPolicy", () => {
  it("shows code in edit mode", () => {
    const policy = computeRenderPolicy({
      mode: "edit",
      showAppCode: false, // ignored in edit mode
      hasCells: true,
      hasCachedOutputs: false,
    });
    expect(policy.showCode).toBe(true);
  });

  it("hides code in present mode regardless of config", () => {
    const policy = computeRenderPolicy({
      mode: "present",
      showAppCode: true,
      hasCells: true,
      hasCachedOutputs: true,
    });
    expect(policy.showCode).toBe(false);
  });

  it("respects showAppCode in read mode", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: true,
        hasCells: true,
        hasCachedOutputs: false,
      }).showCode,
    ).toBe(true);

    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
      }).showCode,
    ).toBe(false);
  });
});

describe("computeRenderPolicy.canPaint", () => {
  it("is false when no cells exist", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: true,
        hasCells: false,
        hasCachedOutputs: false,
      }).canPaint,
    ).toBe(false);
  });

  it("is true in edit mode whenever cells exist", () => {
    expect(
      computeRenderPolicy({
        mode: "edit",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
      }).canPaint,
    ).toBe(true);
  });

  it("is true in read mode when code is visible", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: true,
        hasCells: true,
        hasCachedOutputs: false,
      }).canPaint,
    ).toBe(true);
  });

  it("is false in headless read mode without cached outputs", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
      }).canPaint,
    ).toBe(false);
  });

  it("is true in headless read mode with cached outputs", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: true,
      }).canPaint,
    ).toBe(true);
  });
});
