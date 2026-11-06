/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import type { ChatStatus } from "ai";
import {
  isChatBusy,
  useChatGeneration,
} from "@/components/chat/use-chat-generation";
import { cellId } from "@/__tests__/branded";
import { TooltipProvider } from "@/components/ui/tooltip";
import { stagedAICellsAtom } from "@/core/ai/staged-cells";
import { scrollAndHighlightCell } from "../../../links/cell-link";
import { PendingAICells } from "../pending-ai-cells";
import { PendingAIChangesBadge } from "../pending-ai-changes-badge";

const deleteCell = vi.hoisted(() => vi.fn());
const setCellCode = vi.hoisted(() => vi.fn());

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => deleteCell,
}));

vi.mock("@/core/cells/cells", () => ({
  getCellEditorView: vi.fn(),
}));
vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({
    createCell: vi.fn(),
    setCellCode,
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

    fireEvent.click(screen.getByRole("button", { name: "Cell 1 of 3" }));
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("Cell 1 of 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("Cell 2 of 3")).toBeInTheDocument();

    fireEvent.click(previous);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("Cell 1 of 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("Cell 2 of 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(third, "focus");
    expect(screen.getByText("Cell 3 of 3")).toBeInTheDocument();

    fireEvent.click(next);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(first, "focus");
    expect(screen.getByText("Cell 1 of 3")).toBeInTheDocument();

    fireEvent.click(previous);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(third, "focus");
    expect(screen.getByText("Cell 3 of 3")).toBeInTheDocument();
  });
});

function ChatGeneration({ status }: { status: ChatStatus }) {
  useChatGeneration(isChatBusy(status));
  return null;
}

it("locks staged edits during generation and unlocks after completion, stop, error, or unmount", () => {
  const store = createStore();
  const pendingCell = cellId("pending-cell");
  store.set(
    stagedAICellsAtom,
    new Map([
      [pendingCell, { type: "add_cell" }],
      [cellId("other-pending-cell"), { type: "add_cell" }],
    ]),
  );
  const ui = (status?: ChatStatus) => (
    <Provider store={store}>
      <TooltipProvider>
        {status && <ChatGeneration status={status} />}
        <PendingAICells />
      </TooltipProvider>
    </Provider>
  );
  const { rerender } = render(ui("ready"));
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
    const keep = screen.getByRole("button", { name: "Keep all" });
    expect(keep.hasAttribute("disabled")).toBe(isGenerating);
    expect(
      screen.queryByRole("button", { name: "Keep all" }),
    ).toBeInTheDocument();
    const keepCell = screen.getByRole("button", { name: "Keep" });
    const discardCell = screen.getByRole("button", { name: "Discard" });
    for (const button of [keepCell, discardCell]) {
      expect(button.hasAttribute("disabled")).toBe(isGenerating);
      if (isGenerating) {
        fireEvent.click(button);
      }
    }
    expect(store.get(stagedAICellsAtom).has(pendingCell)).toBe(true);
    expect(screen.queryByRole("button", { name: "Keep" })).toBeInTheDocument();
  }

  fireEvent.click(screen.getByRole("button", { name: "Keep all" }));
  expect(store.get(stagedAICellsAtom).size).toBe(0);
});

it.each(["Delete cell", "Keep cell"])(
  "resolves a proposed deletion with %s and advances review",
  (label) => {
    deleteCell.mockClear();
    const store = createStore();
    const first = cellId("deleted-cell");
    const second = cellId("added-cell");
    store.set(
      stagedAICellsAtom,
      new Map([
        [first, { type: "delete_cell", previousCode: "x = 1" }],
        [second, { type: "add_cell" }],
      ]),
    );
    render(
      <Provider store={store}>
        <PendingAICells />
      </Provider>,
    );
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(store.get(stagedAICellsAtom).has(first)).toBe(false);
    expect(deleteCell).toHaveBeenCalledTimes(label === "Delete cell" ? 1 : 0);
    expect(scrollAndHighlightCell).toHaveBeenLastCalledWith(second, "focus");
    expect(screen.getByText("1 cell changed")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Keep all" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Discard all" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(
      screen.queryByRole("region", { name: "Review AI changes" }),
    ).not.toBeInTheDocument();
  },
);

it("keeps batch discard visible and locks it during generation", () => {
  deleteCell.mockClear();
  const store = createStore();
  const pendingCell = cellId("discarded-cell");
  store.set(
    stagedAICellsAtom,
    new Map([
      [pendingCell, { type: "add_cell" }],
      [cellId("other-pending-cell"), { type: "add_cell" }],
    ]),
  );
  const ui = (status: ChatStatus) => (
    <Provider store={store}>
      <ChatGeneration status={status} />
      <PendingAICells />
    </Provider>
  );
  const { rerender } = render(ui("streaming"));
  const discard = screen.getByRole("button", { name: "Discard all" });
  expect(discard).toBeVisible();
  expect(discard).toBeDisabled();
  fireEvent.click(discard);
  expect(store.get(stagedAICellsAtom).has(pendingCell)).toBe(true);
  rerender(ui("ready"));
  expect(discard).toBeEnabled();
  fireEvent.click(discard);
  expect(deleteCell).toHaveBeenCalledTimes(2);
  expect(deleteCell).toHaveBeenCalledWith({ cellId: pendingCell });
  expect(store.get(stagedAICellsAtom).size).toBe(0);
});

it("clears the panel badge when all pending changes are accepted", () => {
  const store = createStore();
  store.set(
    stagedAICellsAtom,
    new Map([[cellId("pending"), { type: "add_cell" }]]),
  );
  render(
    <Provider store={store}>
      <PendingAIChangesBadge />
      <PendingAICells />
    </Provider>,
  );
  expect(screen.getByText("1 pending AI change")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Keep" }));
  expect(screen.queryByText("1 pending AI change")).not.toBeInTheDocument();
});

it("discards an edit to a cell whose editor is not mounted", () => {
  setCellCode.mockClear();
  const store = createStore();
  const collapsed = cellId("collapsed-cell");
  store.set(
    stagedAICellsAtom,
    new Map([[collapsed, { type: "update_cell", previousCode: "x = 1" }]]),
  );
  render(
    <Provider store={store}>
      <PendingAICells />
    </Provider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Discard" }));
  expect(setCellCode).toHaveBeenCalledWith({
    cellId: collapsed,
    code: "x = 1",
  });
  expect(store.get(stagedAICellsAtom).size).toBe(0);
});
