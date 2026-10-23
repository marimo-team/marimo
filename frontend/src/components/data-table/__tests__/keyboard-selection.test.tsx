/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { CellSelectionState } from "../cell-selection/types";
import { DataTable } from "../data-table";

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
  afterEach(() => vi.useRealTimers());

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
