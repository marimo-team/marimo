/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import {
  stagedAICellsAtom,
  stagedGenerationInProgressAtom,
} from "@/core/ai/staged-cells";
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
    store.set(stagedGenerationInProgressAtom, true);

    const { rerender } = render(
      <Provider store={store}>
        <StagedAICellFooter cellId={generatedCellId} />
      </Provider>,
    );

    expect(screen.getByRole("button", { name: "Accept" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();

    store.set(stagedGenerationInProgressAtom, false);
    rerender(
      <Provider store={store}>
        <StagedAICellFooter cellId={generatedCellId} />
      </Provider>,
    );

    expect(screen.getByRole("button", { name: "Accept" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
  });
});
