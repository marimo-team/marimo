/* Copyright 2026 Marimo. All rights reserved. */
import type { ColumnDef } from "@tanstack/react-table";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DataTable } from "../data-table";

// Regression tests for #10787: in narrow tables (<= 4 columns) a filler
// column takes the leftover width. The last real column must not draw a
// right border, or the empty filler looks like an extra column.

type Row = Record<string, string>;

function renderTable(
  columnIds: string[],
  extraProps: Partial<React.ComponentProps<typeof DataTable<Row>>> = {},
) {
  const columns: ColumnDef<Row>[] = columnIds.map((id) => ({
    id,
    accessorKey: id,
    header: id,
  }));
  const data: Row[] = [Object.fromEntries(columnIds.map((id) => [id, id]))];
  return render(
    <TooltipProvider>
      <DataTable
        data={data}
        columns={columns}
        totalRows={1}
        totalColumns={columnIds.length}
        pagination={false}
        {...extraProps}
      />
    </TooltipProvider>,
  );
}

function headerCells(container: HTMLElement) {
  return [...container.querySelectorAll("thead tr th")];
}

function firstRowCells(container: HTMLElement) {
  return [...container.querySelectorAll("tbody tr:first-child td")];
}

const isFiller = (el: Element) => el.getAttribute("aria-hidden") === "true";
const hasNoRightBorder = (el: Element) => el.classList.contains("border-r-0");

describe("filler column border (#10787)", () => {
  it("removes the right border of the last column in a narrow table", () => {
    const { container } = renderTable(["key", "value"]);

    for (const cells of [headerCells(container), firstRowCells(container)]) {
      expect(cells).toHaveLength(3);
      expect(isFiller(cells[2])).toBe(true);
      expect(hasNoRightBorder(cells[0])).toBe(false);
      expect(hasNoRightBorder(cells[1])).toBe(true);
    }
  });

  it("still renders the filler at exactly 4 columns", () => {
    const { container } = renderTable(["a", "b", "c", "d"]);

    for (const cells of [headerCells(container), firstRowCells(container)]) {
      expect(cells).toHaveLength(5);
      expect(isFiller(cells[4])).toBe(true);
      expect(hasNoRightBorder(cells[3])).toBe(true);
      expect(cells.slice(0, 3).some(hasNoRightBorder)).toBe(false);
    }
  });

  it("keeps every border and has no filler for wider tables", () => {
    const { container } = renderTable(["a", "b", "c", "d", "e"]);

    for (const cells of [headerCells(container), firstRowCells(container)]) {
      expect(cells).toHaveLength(5);
      expect(cells.some(isFiller)).toBe(false);
      expect(cells.some(hasNoRightBorder)).toBe(false);
    }
  });

  it("removes the border from the right-pinned column, which renders last", () => {
    const { container } = renderTable(["a", "b", "c"], {
      freezeColumnsRight: ["a"],
    });

    for (const cells of [headerCells(container), firstRowCells(container)]) {
      expect(cells).toHaveLength(4);
      expect(cells[2].textContent).toContain("a");
      expect(hasNoRightBorder(cells[2])).toBe(true);
      expect(hasNoRightBorder(cells[0])).toBe(false);
      expect(hasNoRightBorder(cells[1])).toBe(false);
    }
  });

  it("does not crash on an empty table", () => {
    const columns: ColumnDef<Row>[] = [{ id: "a", accessorKey: "a" }];
    expect(() =>
      render(
        <TooltipProvider>
          <DataTable
            data={[]}
            columns={columns}
            totalRows={0}
            totalColumns={1}
            pagination={false}
          />
        </TooltipProvider>,
      ),
    ).not.toThrow();
  });
});
