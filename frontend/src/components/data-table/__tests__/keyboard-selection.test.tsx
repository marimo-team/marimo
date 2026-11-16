/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { copyToClipboard } from "@/utils/copy";
import type { CellSelectionState } from "../cell-selection/types";
import { DataTable } from "../data-table";

vi.mock("@/utils/copy", () => ({ copyToClipboard: vi.fn() }));

function SelectableTable({ multiple = false }: { multiple?: boolean }) {
  const [selection, setSelection] = useState<CellSelectionState>([]);
  return (
    <TooltipProvider>
      <DataTable
        data={[{ name: "Alice" }, { name: "Bob" }]}
        columns={[{ accessorKey: "name", header: "Name" }]}
        totalRows={2}
        totalColumns={1}
        pagination={false}
        selection={multiple ? "multi-cell" : "single-cell"}
        cellSelection={selection}
        onCellSelectionChange={setSelection}
      />
    </TooltipProvider>
  );
}

describe("table keyboard access", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("includes the initial focused cell when extending a keyboard range", () => {
    render(<SelectableTable />);
    const [alice, bob] = screen.getAllByRole("gridcell");
    act(() => alice.focus());
    fireEvent.keyDown(alice, { key: "ArrowDown", shiftKey: true });
    fireEvent.keyDown(bob, { key: "c", ctrlKey: true });
    expect(copyToClipboard).toHaveBeenLastCalledWith("Alice\nBob", undefined);
    fireEvent.keyDown(bob, { key: "ArrowUp", shiftKey: true });
    fireEvent.keyDown(alice, { key: "c", ctrlKey: true });
    expect(copyToClipboard).toHaveBeenLastCalledWith("Alice", undefined);
  });

  it.each(["Enter", " "])(
    "copies the activated cell with %s, including after an older selection",
    (key) => {
      render(<SelectableTable />);
      const [alice, bob] = screen.getAllByRole("gridcell");
      for (const [cell, value] of [
        [alice, "Alice"],
        [bob, "Bob"],
      ] as const) {
        act(() => cell.focus());
        fireEvent.keyDown(cell, { key });
        fireEvent.keyDown(cell, { key: "c", ctrlKey: true });
        expect(copyToClipboard).toHaveBeenLastCalledWith(value, undefined);
        expect(cell).toHaveAttribute("aria-selected", "true");
      }
    },
  );

  it("moves focus and activation together inside a shadow root", () => {
    vi.useFakeTimers();
    const host = document.createElement("div");
    document.body.append(host);
    const shadow = host.attachShadow({ mode: "open" });
    const container = document.createElement("div");
    shadow.append(container);
    const view = render(<SelectableTable />, { container });
    try {
      const [alice, bob] = within(container).getAllByRole("gridcell");
      alice.scrollIntoView = vi.fn();
      bob.scrollIntoView = vi.fn();
      act(() => alice.focus());
      fireEvent.keyDown(alice, { key: "ArrowDown" });
      act(() => vi.runAllTimers());
      expect(shadow.activeElement).toBe(bob);
      fireEvent.keyDown(bob, { key: " " });
      expect(bob).toHaveAttribute("aria-selected", "true");
      expect(alice).toHaveAttribute("aria-selected", "false");
    } finally {
      view.unmount();
      host.remove();
    }
  });

  it("does not move focus away from a nested control after navigation", () => {
    vi.useFakeTimers();
    render(<SelectableTable />);
    const [alice, bob] = screen.getAllByRole("gridcell");
    alice.scrollIntoView = vi.fn();
    bob.scrollIntoView = vi.fn();
    const button = document.createElement("button");
    alice.append(button);
    act(() => alice.focus());
    fireEvent.keyDown(alice, { key: "ArrowDown" });
    act(() => {
      button.focus();
      vi.runAllTimers();
    });
    expect(button).toHaveFocus();
  });

  it("ignores stale scheduled focus when moving between cells", () => {
    vi.useFakeTimers();
    render(<SelectableTable />);
    const [alice, bob] = screen.getAllByRole("gridcell");
    alice.scrollIntoView = vi.fn();
    bob.scrollIntoView = vi.fn();
    act(() => {
      alice.focus();
      bob.focus();
      vi.runAllTimers();
    });
    expect(bob).toHaveFocus();
    expect(alice.scrollIntoView).not.toHaveBeenCalled();
    expect(bob.scrollIntoView).toHaveBeenCalledOnce();
    expect(vi.getTimerCount()).toBe(0);
  });
  it.each([false, true])(
    "selects focused cells without a preceding click (multiple=%s)",
    (multiple) => {
      render(<SelectableTable multiple={multiple} />);
      const [alice, bob] = screen.getAllByRole("gridcell");
      alice.focus();
      fireEvent.keyDown(alice, { key: "Enter" });
      expect(alice).toHaveAttribute("aria-selected", "true");
      bob.focus();
      fireEvent.keyDown(bob, { key: " " });
      expect(bob).toHaveAttribute("aria-selected", "true");
      expect(alice).toHaveAttribute("aria-selected", String(multiple));
      fireEvent.keyDown(bob, { key: " " });
      expect(bob).toHaveAttribute("aria-selected", "false");
    },
  );

  it("does not intercept keys from embedded buttons", () => {
    const select = vi.fn();
    render(
      <TooltipProvider>
        <DataTable
          data={[{ name: "Alice" }]}
          columns={[
            {
              accessorKey: "name",
              cell: () => <button type="button">Open person</button>,
            },
          ]}
          totalRows={1}
          totalColumns={1}
          pagination={false}
          selection="single-cell"
          onCellSelectionChange={select}
        />
      </TooltipProvider>,
    );
    const button = screen.getByRole("button", { name: "Open person" });
    for (const key of ["Enter", " ", "ArrowDown"]) {
      expect(fireEvent.keyDown(button, { key })).toBe(true);
    }
    expect(select).not.toHaveBeenCalled();
  });

  it("names search controls and clears a query", () => {
    render(
      <TooltipProvider>
        <DataTable
          data={[{ name: "Alice" }]}
          columns={[{ accessorKey: "name" }]}
          totalRows={1}
          totalColumns={1}
          pagination={false}
          showSearch={true}
          onSearchQueryChange={vi.fn()}
        />
      </TooltipProvider>,
    );
    const search = screen.getByRole("textbox", { name: "Search table" });
    fireEvent.change(search, { target: { value: "Alice" } });
    fireEvent.click(screen.getByRole("button", { name: "Clear table search" }));
    expect(search).toHaveValue("");
  });
});
