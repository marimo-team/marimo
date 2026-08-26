/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen, within } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { stagedAICellsAtom, visibleForTesting } from "@/core/ai/staged-cells";
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
    });

    const view = (
      <Provider store={store}>
        <TooltipProvider>
          <PendingAICells />
        </TooltipProvider>
      </Provider>
    );
    const { rerender } = render(view);

    const acceptButton = screen.getByRole("button", { name: "Accept all" });
    const acceptButtons = within(
      acceptButton.parentElement as HTMLElement,
    ).getAllByRole("button");
    expect(acceptButtons).toHaveLength(2);
    for (const button of acceptButtons) {
      expect(button).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: "Reject all" })).toBeDisabled();

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
    expect(screen.getByRole("button", { name: "Reject all" })).toBeEnabled();
  });
});
