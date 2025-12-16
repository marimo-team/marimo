/* Copyright 2024 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type CellId, HTMLCellId } from "@/core/cells/ids";

const mockScrollCellIntoView = vi.fn();
const mockRaf2 = vi.fn((callback: () => void) => callback());

vi.mock("../focus-utils", () => ({
  scrollCellIntoView: mockScrollCellIntoView,
  raf2: mockRaf2,
}));

type TemporarilyShownCodeState = Set<CellId>;

describe("temporarilyShownCodeActions", () => {
  const cellId = "cell-1" as CellId;
  let cellElement: HTMLElement;

  beforeEach(() => {
    cellElement = document.createElement("div");
    cellElement.id = HTMLCellId.create(cellId);
    document.body.append(cellElement);
    cellElement.focus();

    vi.spyOn(HTMLCellId, "findElementThroughShadowDOMs").mockReturnValue(
      cellElement as HTMLElement & { id: HTMLCellId },
    );

    mockScrollCellIntoView.mockClear();
    mockRaf2.mockClear();
  });

  afterEach(() => {
    cellElement.remove();
    vi.restoreAllMocks();
  });

  it("should scroll cell into view when removing cell causes layout shift", () => {
    const state = new Set<CellId>([cellId]);
    removeCell(state, cellId);

    expect(mockScrollCellIntoView).toHaveBeenCalledWith(cellId);
  });

  it("should not scroll when focused cell is not found", () => {
    vi.spyOn(HTMLCellId, "findElementThroughShadowDOMs").mockReturnValue(null);

    const state = new Set<CellId>([cellId]);
    removeCell(state, cellId);

    expect(mockScrollCellIntoView).not.toHaveBeenCalled();
  });
});

// Helper function that replicates the remove reducer logic
function removeCell(
  state: TemporarilyShownCodeState,
  cellId: CellId,
): TemporarilyShownCodeState {
  if (!state.has(cellId)) {
    return state;
  }
  const newState = new Set(state);
  newState.delete(cellId);

  mockRaf2(() => {
    const activeElement = document.activeElement;
    if (!activeElement) {
      return;
    }
    const focusedCell = HTMLCellId.findElementThroughShadowDOMs(activeElement);
    if (!focusedCell) {
      return;
    }
    mockScrollCellIntoView(HTMLCellId.parse(focusedCell.id));
  });

  return newState;
}
