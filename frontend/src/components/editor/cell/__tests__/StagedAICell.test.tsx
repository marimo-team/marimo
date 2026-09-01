/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { stagedAICellsAtom, visibleForTesting } from "@/core/ai/staged-cells";
import { StagedAICellFooter } from "../StagedAICell";

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

vi.mock("../useRunCells", () => ({
  useRunCell: () => undefined,
}));

describe("StagedAICellFooter", () => {
  it("disables cell actions until generation is complete", () => {
    const store = createStore();
    const generatedCellId = cellId("generated-cell");
    store.set(
      stagedAICellsAtom,
      new Map([[generatedCellId, { type: "add_cell" }]]),
    );
    store.set(visibleForTesting.stagedGenerationAtom, {
      id: Symbol("staged-cell-generation"),
      status: "in_progress",
      cellIds: [generatedCellId],
    });

    const { rerender } = render(
      <Provider store={store}>
        <TooltipProvider>
          <StagedAICellFooter cellId={generatedCellId} />
        </TooltipProvider>
      </Provider>,
    );

    expect(screen.getByRole("button", { name: "Keep cell" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Discard cell" })).toBeDisabled();

    store.set(visibleForTesting.stagedGenerationAtom, null);
    rerender(
      <Provider store={store}>
        <TooltipProvider>
          <StagedAICellFooter cellId={generatedCellId} />
        </TooltipProvider>
      </Provider>,
    );

    expect(screen.getByRole("button", { name: "Keep cell" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Discard cell" })).toBeEnabled();
  });
});
