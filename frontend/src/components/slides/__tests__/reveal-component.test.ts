/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import type { SlideConfig } from "../../editor/renderers/slides-layout/types";
import { shouldShowCode } from "../reveal-component";

const A = cellId("a");

const cells = (
  ...entries: Array<[CellId, SlideConfig]>
): ReadonlyMap<CellId, SlideConfig> => new Map(entries);

describe("shouldShowCode", () => {
  it("is off when the code toggle is unavailable, regardless of config/override", () => {
    expect(
      shouldShowCode({
        cells: cells([A, { showCode: true }]),
        cellId: A,
        showCodeOverrides: new Set([A]),
        codeToggleEnabled: false,
      }),
    ).toBe(false);
  });

  it("is off when there is no active cell", () => {
    expect(
      shouldShowCode({
        cells: cells([A, { showCode: true }]),
        cellId: undefined,
        showCodeOverrides: new Set(),
        codeToggleEnabled: true,
      }),
    ).toBe(false);
  });

  it("follows the persisted config when there is no override", () => {
    expect(
      shouldShowCode({
        cells: cells([A, { showCode: true }]),
        cellId: A,
        showCodeOverrides: new Set(),
        codeToggleEnabled: true,
      }),
    ).toBe(true);
    // Missing config entry defaults to off.
    expect(
      shouldShowCode({
        cells: cells(),
        cellId: A,
        showCodeOverrides: new Set(),
        codeToggleEnabled: true,
      }),
    ).toBe(false);
  });

  it("shows code when either the config or the override is set (logical OR)", () => {
    // Peek: config unset, override present -> shown.
    expect(
      shouldShowCode({
        cells: cells(),
        cellId: A,
        showCodeOverrides: new Set([A]),
        codeToggleEnabled: true,
      }),
    ).toBe(true);
    // Configured + override present -> still shown; the override never hides.
    expect(
      shouldShowCode({
        cells: cells([A, { showCode: true }]),
        cellId: A,
        showCodeOverrides: new Set([A]),
        codeToggleEnabled: true,
      }),
    ).toBe(true);
  });
});
