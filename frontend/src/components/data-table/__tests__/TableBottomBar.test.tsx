/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import { getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CellSelectionProvider } from "../range-focus/provider";
import { TableBottomBar } from "../TableBottomBar";

function renderWithTable(opts: {
  totalColumns: number;
  hiddenColumns?: string[];
}) {
  const Wrapper = () => {
    const table = useReactTable({
      data: [] as Array<Record<string, unknown>>,
      columns: Array.from({ length: opts.totalColumns }, (_, i) => ({
        id: `col${i}`,
        enableHiding: true,
      })),
      getCoreRowModel: getCoreRowModel(),
      locale: "en-US",
      state: {
        columnVisibility: Object.fromEntries(
          (opts.hiddenColumns ?? []).map((c) => [c, false]),
        ),
      },
    });

    return (
      <TableBottomBar
        pagination={false}
        totalColumns={opts.totalColumns}
        table={table}
      />
    );
  };

  return render(
    <TooltipProvider>
      <CellSelectionProvider>
        <Wrapper />
      </CellSelectionProvider>
    </TooltipProvider>,
  );
}

describe("TableBottomBar — hidden column count", () => {
  it("does not render '(n hidden)' when no columns are hidden", () => {
    renderWithTable({ totalColumns: 3 });
    expect(screen.queryByText(/hidden/)).toBeNull();
  });

  it("renders 'X visible (n hidden)' when columns are hidden", () => {
    renderWithTable({ totalColumns: 3, hiddenColumns: ["col1"] });
    expect(screen.getByText(/2 visible/)).toBeInTheDocument();
    expect(screen.getByText(/\(1 hidden\)/)).toBeInTheDocument();
  });

  it("renders '(n hidden)' as inert text, not a button", () => {
    renderWithTable({ totalColumns: 3, hiddenColumns: ["col1"] });
    const suffix = screen.getByText(/\(1 hidden\)/);
    expect(suffix.tagName).toBe("SPAN");
    expect(suffix.closest("button")).toBeNull();
  });
});
