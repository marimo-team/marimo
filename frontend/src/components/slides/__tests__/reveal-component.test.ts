/* Copyright 2026 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import type { RuntimeCell } from "@/core/cells/types";
import type { SlideConfig } from "../../editor/renderers/slides-layout/types";
import {
  deckSlideType,
  parkedRendersSource,
  shouldShowCode,
  useParkedPreview,
} from "../reveal-component";

const A = cellId("a");
const B = cellId("b");

const cells = (
  ...entries: Array<[CellId, SlideConfig]>
): ReadonlyMap<CellId, SlideConfig> => new Map(entries);

// The hook only reads `cell.id`, so a minimal stub is enough. Cast is confined
// to this test helper (see `@/__tests__/branded` for the same rationale).
const cell = (id: CellId): RuntimeCell => ({ id }) as RuntimeCell;

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

describe("deckSlideType", () => {
  const NONE_IDS: ReadonlySet<CellId> = new Set();

  it("uses the configured type for a normal cell", () => {
    expect(
      deckSlideType({
        cell: cell(A),
        noOutputIds: NONE_IDS,
        heldEditCellId: null,
        slideConfigs: cells([A, { type: "fragment" }]),
      }),
    ).toBe("fragment");
  });

  it("defaults to a top-level slide when no type is configured", () => {
    expect(
      deckSlideType({
        cell: cell(A),
        noOutputIds: NONE_IDS,
        heldEditCellId: null,
        slideConfigs: cells(),
      }),
    ).toBe("slide");
  });

  it("drops output-less cells from the deck", () => {
    expect(
      deckSlideType({
        cell: cell(A),
        noOutputIds: new Set([A]),
        heldEditCellId: null,
        // Even an explicit type is overridden by the skip.
        slideConfigs: cells([A, { type: "sub-slide" }]),
      }),
    ).toBe("skip");
  });

  it("drops the held-edit cell so it isn't mounted twice", () => {
    expect(
      deckSlideType({
        cell: cell(A),
        noOutputIds: NONE_IDS,
        heldEditCellId: A,
        slideConfigs: cells([A, { type: "slide" }]),
      }),
    ).toBe("skip");
  });
});

describe("parkedRendersSource", () => {
  it("follows `showCode` for a cell that has output", () => {
    expect(
      parkedRendersSource({
        isNoOutputPreview: false,
        isEditable: false,
        showCode: true,
      }),
    ).toBe(true);
    expect(
      parkedRendersSource({
        isNoOutputPreview: false,
        isEditable: true,
        showCode: false,
      }),
    ).toBe(false);
  });

  it("falls back to source for an editable no-output cell even when showCode is off", () => {
    expect(
      parkedRendersSource({
        isNoOutputPreview: true,
        isEditable: true,
        showCode: false,
      }),
    ).toBe(true);
  });

  it("renders output for a read-only no-output cell with showCode off", () => {
    expect(
      parkedRendersSource({
        isNoOutputPreview: true,
        isEditable: false,
        showCode: false,
      }),
    ).toBe(false);
  });
});

describe("useParkedPreview", () => {
  const NO_CONFIG = cells();
  const NONE = new Set<CellId>();

  it("is inert for a rendered cell with output", () => {
    const { result } = renderHook(() =>
      useParkedPreview({
        activeCell: cell(A),
        slideConfigs: NO_CONFIG,
        noOutputIds: NONE,
      }),
    );
    expect(result.current).toEqual({
      parkedPreviewCell: null,
      isHeldEdit: false,
      isNoOutputPreview: false,
      heldEditCellId: null,
    });
  });

  it("is inert when there is no active cell", () => {
    const { result } = renderHook(() =>
      useParkedPreview({
        activeCell: undefined,
        slideConfigs: NO_CONFIG,
        noOutputIds: NONE,
      }),
    );
    expect(result.current).toEqual({
      parkedPreviewCell: null,
      isHeldEdit: false,
      isNoOutputPreview: false,
      heldEditCellId: null,
    });
  });

  it("parks a skipped cell without flagging it as a no-output preview", () => {
    const { result } = renderHook(() =>
      useParkedPreview({
        activeCell: cell(A),
        slideConfigs: cells([A, { type: "skip" }]),
        noOutputIds: NONE,
      }),
    );
    expect(result.current).toEqual({
      parkedPreviewCell: cell(A),
      isHeldEdit: false,
      isNoOutputPreview: false,
      heldEditCellId: null,
    });
  });

  it("parks an output-less cell as a no-output preview", () => {
    const { result } = renderHook(() =>
      useParkedPreview({
        activeCell: cell(A),
        slideConfigs: NO_CONFIG,
        noOutputIds: new Set([A]),
      }),
    );
    expect(result.current).toEqual({
      parkedPreviewCell: cell(A),
      isHeldEdit: false,
      isNoOutputPreview: true,
      heldEditCellId: null,
    });
  });

  it("holds the cell in the overlay once it gains output", () => {
    const { result, rerender } = renderHook(
      (props: Parameters<typeof useParkedPreview>[0]) =>
        useParkedPreview(props),
      {
        initialProps: {
          activeCell: cell(A),
          slideConfigs: NO_CONFIG,
          noOutputIds: new Set([A]),
        },
      },
    );
    expect(result.current.isNoOutputPreview).toBe(true);
    expect(result.current.isHeldEdit).toBe(false);

    // Same cell, now with output: keep it parked so the editor isn't remounted.
    rerender({
      activeCell: cell(A),
      slideConfigs: NO_CONFIG,
      noOutputIds: NONE,
    });
    expect(result.current).toEqual({
      parkedPreviewCell: cell(A),
      isHeldEdit: true,
      isNoOutputPreview: false,
      heldEditCellId: A,
    });
  });

  it("releases the hold when a different cell becomes active", () => {
    const { result, rerender } = renderHook(
      (props: Parameters<typeof useParkedPreview>[0]) =>
        useParkedPreview(props),
      {
        initialProps: {
          activeCell: cell(A),
          slideConfigs: NO_CONFIG,
          noOutputIds: new Set([A]),
        },
      },
    );
    // Arm the hold, then let A gain output (held).
    rerender({
      activeCell: cell(A),
      slideConfigs: NO_CONFIG,
      noOutputIds: NONE,
    });
    expect(result.current.isHeldEdit).toBe(true);

    // Navigate to a rendered B: the hold on A is released.
    rerender({
      activeCell: cell(B),
      slideConfigs: NO_CONFIG,
      noOutputIds: NONE,
    });
    expect(result.current).toEqual({
      parkedPreviewCell: null,
      isHeldEdit: false,
      isNoOutputPreview: false,
      heldEditCellId: null,
    });
  });
});
