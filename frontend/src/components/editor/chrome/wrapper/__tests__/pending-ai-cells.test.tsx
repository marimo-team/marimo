/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import type { ChatStatus } from "ai";
import { useChatGeneration } from "@/components/chat/use-chat-generation";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { stagedAICellsAtom } from "@/core/ai/staged-cells";
import { scrollAndHighlightCell } from "../../../links/cell-link";
import { StagedAICellFooter } from "../../../cell/StagedAICell";
import { PendingAICells } from "../pending-ai-cells";

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => vi.fn(),
}));

vi.mock("@/core/cells/cells", () => ({
  getCellEditorView: vi.fn(),
}));
vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({
    createCell: vi.fn(),
    setCellCode: vi.fn(),
  }),
}));

vi.mock("@/components/editor/cell/useRunCells", () => ({
  useRunCells: () => vi.fn(),
  useRunCell: () => vi.fn(),
}));

vi.mock("@/components/editor/links/cell-link", () => ({
  scrollAndHighlightCell: vi.fn(),
}));

describe("PendingAICells", () => {
  it("navigates between pending cells through named controls", () => {
    const store = createStore();
    const first = cellId("first-pending-cell");
    const second = cellId("second-pending-cell");
    const third = cellId("third-pending-cell");
    store.set(
      stagedAICellsAtom,
      new Map([
        [first, { type: "add_cell" }],
        [second, { type: "add_cell" }],
        [third, { type: "add_cell" }],
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
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("1 / 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("2 / 3")).toBeInTheDocument();

    fireEvent.click(previous);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("1 / 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("2 / 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(third, "focus");
    expect(screen.getByText("3 / 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("1 / 3")).toBeInTheDocument();

    fireEvent.click(previous);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(third, "focus");
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
  });
});

function ChatGeneration({ status }: { status: ChatStatus }) {
  useChatGeneration(status);
  return null;
}

it("locks staged edits during generation and unlocks after completion, stop, error, or unmount", () => {
  const store = createStore();
  const pendingCell = cellId("pending-cell");
  store.set(stagedAICellsAtom, new Map([[pendingCell, { type: "add_cell" }]]));
  const ui = (status?: ChatStatus) => (
    <Provider store={store}>
      <TooltipProvider>
        {status && <ChatGeneration status={status} />}
        <PendingAICells />
        <StagedAICellFooter cellId={pendingCell} />
      </TooltipProvider>
    </Provider>
  );
  const { rerender } = render(ui("ready"));
  const keep = screen.getByRole("button", { name: "Keep all" });
  const discard = screen.getByRole("button", { name: "Discard all" });
  const keepCell = screen.getByRole("button", { name: "Keep cell" });
  const discardCell = screen.getByRole("button", { name: "Discard cell" });
  const keepAndRun = keep.parentElement!.querySelectorAll("button")[1];
  for (const status of [
    "submitted",
    "streaming",
    "ready",
    "submitted",
    "ready",
    "submitted",
    "error",
    "streaming",
    undefined,
  ] as const) {
    rerender(ui(status));
    const isGenerating = status === "submitted" || status === "streaming";
    for (const button of [keep, discard, keepAndRun, keepCell, discardCell]) {
      expect(button.hasAttribute("disabled")).toBe(isGenerating);
      if (isGenerating) {
        fireEvent.click(button);
      }
    }
    expect(store.get(stagedAICellsAtom).has(pendingCell)).toBe(true);
  }

  fireEvent.click(keep);
  expect(store.get(stagedAICellsAtom).size).toBe(0);
});
