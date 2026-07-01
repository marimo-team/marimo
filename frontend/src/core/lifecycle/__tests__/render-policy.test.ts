/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { visibleForTesting } from "../render-policy";

const { computeRenderPolicy } = visibleForTesting;

const originalHref = window.location.href;
function setSearch(search: string) {
  window.history.replaceState(null, "", `/${search}`);
}

describe("computeRenderPolicy", () => {
  it("shows code in edit mode", () => {
    const policy = computeRenderPolicy({
      mode: "edit",
      showAppCode: false, // ignored in edit mode
      hasCells: true,
      hasCachedOutputs: false,
      allCellsIdle: false,
    });
    expect(policy.showCode).toBe(true);
  });

  it("hides code in present mode regardless of config", () => {
    const policy = computeRenderPolicy({
      mode: "present",
      showAppCode: true,
      hasCells: true,
      hasCachedOutputs: true,
      allCellsIdle: false,
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
        allCellsIdle: false,
      }).showCode,
    ).toBe(true);

    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
        allCellsIdle: false,
      }).showCode,
    ).toBe(false);
  });

  it("reports showCachedOutputs when cells and cached outputs are present", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: true,
        allCellsIdle: false,
      }).showCachedOutputs,
    ).toBe(true);
  });

  it("does not report showCachedOutputs when there are no cells", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: false,
        hasCachedOutputs: true,
        allCellsIdle: false,
      }).showCachedOutputs,
    ).toBe(false);
  });

  it("only reports showCachedOutputs for real outputs, not an idle notebook", () => {
    // Regression guard: `showCachedOutputs` must stay honest even when the
    // notebook is settled with no outputs (that only affects `canPaint`).
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
        allCellsIdle: true,
      }).showCachedOutputs,
    ).toBe(false);
  });
});

describe("computeRenderPolicy — read-mode code visibility", () => {
  beforeEach(() => {
    setSearch("");
  });

  afterEach(() => {
    window.history.replaceState(null, "", originalHref);
  });

  it("hides code when the server stripped sources (?include-code=false)", () => {
    setSearch("?include-code=false");
    const policy = computeRenderPolicy({
      mode: "read",
      showAppCode: true, // config would show code, but sources are stripped
      hasCells: true,
      hasCachedOutputs: false,
      allCellsIdle: false,
    });
    expect(policy.showCode).toBe(false);
    // With no code, no outputs, and still running, there is nothing to paint.
    expect(policy.canPaint).toBe(false);
  });

  it("include-code=false still paints when cached outputs exist", () => {
    setSearch("?include-code=false");
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: true,
        hasCells: true,
        hasCachedOutputs: true,
        allCellsIdle: false,
      }).canPaint,
    ).toBe(true);
  });
});

describe("computeRenderPolicy.canPaint", () => {
  it("is false when no cells exist, even if all (zero) cells are vacuously idle", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: true,
        hasCells: false,
        hasCachedOutputs: false,
        allCellsIdle: true,
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
        allCellsIdle: false,
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
        allCellsIdle: false,
      }).canPaint,
    ).toBe(true);
  });

  it("is false in headless read mode while the notebook is still running with no outputs", () => {
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
        allCellsIdle: false,
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
        allCellsIdle: false,
      }).canPaint,
    ).toBe(true);
  });

  it("is true in headless read mode for a settled notebook with no outputs", () => {
    // A notebook that ran to completion producing no outputs must still paint
    // (empty) rather than sit on a spinner — parity with the pre-framework
    // `hasAnyOutputAtom` idle fallback.
    expect(
      computeRenderPolicy({
        mode: "read",
        showAppCode: false,
        hasCells: true,
        hasCachedOutputs: false,
        allCellsIdle: true,
      }).canPaint,
    ).toBe(true);
  });

  // In present mode `showCode` is always false, so `canPaint` rides entirely
  // on cached outputs / a settled notebook.
  it("is true in present mode with cached outputs", () => {
    expect(
      computeRenderPolicy({
        mode: "present",
        showAppCode: true,
        hasCells: true,
        hasCachedOutputs: true,
        allCellsIdle: false,
      }).canPaint,
    ).toBe(true);
  });

  it("is false in present mode while still running with no outputs", () => {
    expect(
      computeRenderPolicy({
        mode: "present",
        showAppCode: true,
        hasCells: true,
        hasCachedOutputs: false,
        allCellsIdle: false,
      }).canPaint,
    ).toBe(false);
  });

  it("is true in present mode for a settled notebook with no outputs", () => {
    expect(
      computeRenderPolicy({
        mode: "present",
        showAppCode: true,
        hasCells: true,
        hasCachedOutputs: false,
        allCellsIdle: true,
      }).canPaint,
    ).toBe(true);
  });
});
