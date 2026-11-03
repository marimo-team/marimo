/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import { HTMLCellId, SCRATCH_CELL_ID } from "@/core/cells/ids";
import { goToCellLine } from "@/core/codemirror/go-to-definition/utils";
import { CellLink, CellLinkTraceback } from "../cell-link";

const showCellIfHidden = vi.hoisted(() => vi.fn());
const targetId = cellId("target");

vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({ showCellIfHidden }),
}));
vi.mock("@/core/cells/cells", () => ({
  useCellIds: () => ({ inOrderIds: [targetId] }),
  useCellNames: () => ({ [targetId]: "Target" }),
}));
vi.mock("@/core/saving/filename", () => ({ useFilename: () => "notebook.py" }));
vi.mock("@/core/codemirror/go-to-definition/utils", () => ({
  goToCellLine: vi.fn(),
}));

function flushNavigation() {
  act(() => vi.advanceTimersToNextFrame());
}

describe("CellLink navigation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    showCellIfHidden.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it("focuses, scrolls, and highlights the target on keyboard activation", () => {
    render(
      <>
        <CellLink cellId={targetId} />
        <div
          id={HTMLCellId.create(targetId)}
          tabIndex={-1}
          data-testid="target"
        />
      </>,
    );
    const target = screen.getByTestId("target");
    target.scrollIntoView = vi.fn();
    const focus = vi.spyOn(target, "focus");
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", `#${target.id}`);
    link.focus();
    // Native anchors emit a click with detail=0 when activated with Enter.
    expect(fireEvent.click(link, { detail: 0 })).toBe(false);
    flushNavigation();

    expect(showCellIfHidden).toHaveBeenCalledExactlyOnceWith({
      cellId: targetId,
    });
    expect(target).toHaveFocus();
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(target.scrollIntoView).toHaveBeenCalledExactlyOnceWith({
      behavior: "smooth",
      block: "center",
    });
    expect(target).toHaveClass("focus-outline");
  });

  it("reveals a hidden destination before moving focus", () => {
    function HiddenCell() {
      const [visible, setVisible] = useState(false);
      showCellIfHidden.mockImplementation(() => setVisible(true));
      return (
        <>
          <CellLink cellId={targetId} skipScroll={true} />
          {visible && (
            <div
              id={HTMLCellId.create(targetId)}
              tabIndex={-1}
              data-testid="target"
            />
          )}
        </>
      );
    }
    render(<HiddenCell />);
    expect(screen.queryByTestId("target")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("link"));
    flushNavigation();
    expect(screen.getByTestId("target")).toHaveFocus();
  });

  it.each([
    { metaKey: true },
    { ctrlKey: true },
    { shiftKey: true },
    { altKey: true },
    { button: 1 },
  ])("preserves browser activation for %o", (modifiers) => {
    render(<CellLink cellId={targetId} />);
    const link = screen.getByRole("link");
    link.focus();
    expect(fireEvent.click(link, modifiers)).toBe(true);
    flushNavigation();
    expect(showCellIfHidden).not.toHaveBeenCalled();
    expect(link).toHaveFocus();
  });

  it("lets traceback line navigation choose the final focus", () => {
    render(
      <>
        <CellLinkTraceback cellId={targetId} lineNumber={7} />
        <div
          id={HTMLCellId.create(targetId)}
          tabIndex={-1}
          data-testid="target"
        >
          <textarea aria-label="Editor" />
        </div>
      </>,
    );
    const target = screen.getByTestId("target");
    target.scrollIntoView = vi.fn();
    const editor = screen.getByRole("textbox", { name: "Editor" });
    vi.mocked(goToCellLine).mockImplementation(() => {
      expect(target).toHaveFocus();
      editor.focus();
      return true;
    });
    fireEvent.click(screen.getByRole("link"));
    flushNavigation();
    expect(goToCellLine).toHaveBeenCalledExactlyOnceWith(targetId, 7);
    expect(editor).toHaveFocus();
    expect(target.scrollIntoView).not.toHaveBeenCalled();
  });

  it("keeps scratch references non-navigable", () => {
    render(
      <CellLink cellId={SCRATCH_CELL_ID} formatCellName={() => "scratch"} />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("scratch"));
    flushNavigation();
    expect(showCellIfHidden).not.toHaveBeenCalled();
  });
});
