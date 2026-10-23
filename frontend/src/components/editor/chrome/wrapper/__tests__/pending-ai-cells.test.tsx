/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { stagedAICellsAtom, visibleForTesting } from "@/core/ai/staged-cells";
import { scrollAndHighlightCell } from "../../../links/cell-link";
import { PendingAICells } from "../pending-ai-cells";

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => vi.fn(),
}));

vi.mock("@/core/cells/cells", () => ({
  getCellEditorView: vi.fn(),
  useCellActions: () => ({
    createNewCell: vi.fn(),
    updateCellCode: vi.fn(),
  }),
}));

vi.mock("@/components/editor/cell/useRunCells", () => ({
  useRunCells: () => vi.fn(),
}));

vi.mock("@/components/editor/links/cell-link", () => ({
  scrollAndHighlightCell: vi.fn(),
}));

describe("PendingAICells", () => {
  it("navigates between pending cells through named controls", () => {
    const store = createStore();
    const first = cellId("first-pending-cell");
    const second = cellId("second-pending-cell");
    store.set(
      stagedAICellsAtom,
      new Map([
        [first, { type: "add_cell" }],
        [second, { type: "add_cell" }],
      ]),
    );

    render(
      <Provider store={store}>
        <TooltipProvider>
          <PendingAICells />
        </TooltipProvider>
      </Provider>,
    );

    const next = screen.getByRole("button", { name: "Next pending AI cell" });
    const previous = screen.getByRole("button", {
      name: "Previous pending AI cell",
    });

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("2 / 2")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("1 / 2")).toBeInTheDocument();

    fireEvent.click(previous);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
  });

  it("disables bulk actions while cells are still generating", () => {
    const store = createStore();
    const generationId = Symbol("staged-cell-generation");
    store.set(
      stagedAICellsAtom,
      new Map([[cellId("generated-cell"), { type: "add_cell" }]]),
    );
    store.set(visibleForTesting.stagedGenerationAtom, {
      id: generationId,
      status: "in_progress",
      cellIds: [cellId("generated-cell")],
    });

    const view = (
      <Provider store={store}>
        <TooltipProvider>
          <PendingAICells />
        </TooltipProvider>
      </Provider>
    );
    const { rerender } = render(view);

    const acceptButton = screen.getByRole("button", { name: "Keep all" });
    const acceptButtons = within(
      acceptButton.parentElement as HTMLElement,
    ).getAllByRole("button");
    expect(acceptButtons).toHaveLength(2);
    for (const button of acceptButtons) {
      expect(button).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: "Discard all" })).toBeDisabled();

    act(() => {
      store.set(visibleForTesting.stagedGenerationAtom, {
        id: generationId,
        status: "complete",
      });
    });
    rerender(view);

    for (const button of acceptButtons) {
      expect(button).toBeEnabled();
    }
    expect(screen.getByRole("button", { name: "Discard all" })).toBeEnabled();
  });
});
