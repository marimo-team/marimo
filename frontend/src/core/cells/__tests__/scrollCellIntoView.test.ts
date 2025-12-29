/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";

// Mock the getCellEditorView function
const mockGetCellEditorView = vi.fn();
vi.mock("@/core/cells/cells", () => ({
  getCellEditorView: mockGetCellEditorView,
}));

// Mock the scrollActiveLineIntoView function
const mockScrollActiveLineIntoView = vi.fn();
vi.mock("@/core/codemirror/extensions", () => ({
  scrollActiveLineIntoView: mockScrollActiveLineIntoView,
}));

// Import after mocking
const { scrollCellIntoView } = await import("@/core/cells/scrollCellIntoView");

describe("scrollCellIntoView", () => {
  const cellId = "test-cell-id" as CellId;
  let cellElement: HTMLElement;

  beforeEach(() => {
    cellElement = document.createElement("div");
    cellElement.id = HTMLCellId.create(cellId);
    cellElement.scrollIntoView = vi.fn();
    document.body.append(cellElement);

    mockGetCellEditorView.mockReturnValue(undefined);
    mockScrollActiveLineIntoView.mockClear();
  });

  afterEach(() => {
    cellElement.remove();
  });

  it("should scroll active line when editor has focus", () => {
    const mockEditor = { hasFocus: true };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mockGetCellEditorView.mockReturnValue(mockEditor as any);

    scrollCellIntoView(cellId);

    expect(mockScrollActiveLineIntoView).toHaveBeenCalledWith(mockEditor, {
      behavior: "instant",
    });
    expect(cellElement.scrollIntoView).not.toHaveBeenCalled();
  });

  it("should scroll cell element when editor is not focused", () => {
    scrollCellIntoView(cellId);

    expect(mockScrollActiveLineIntoView).not.toHaveBeenCalled();
    expect(cellElement.scrollIntoView).toHaveBeenCalledWith({
      behavior: "instant",
      block: "nearest",
    });
  });

  it("should log warning when cell element is not found", () => {
    const warnSpy = vi.spyOn(Logger, "warn").mockImplementation(vi.fn());
    cellElement.remove();

    scrollCellIntoView(cellId);

    expect(warnSpy).toHaveBeenCalledWith(
      `[CellFocusManager] scrollCellIntoView: element not found: ${cellId}`,
    );
    warnSpy.mockRestore();
  });
});
