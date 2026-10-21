/* Copyright 2026 Marimo. All rights reserved. */

import { type Cell, createTable, getCoreRowModel } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { DataTableContextMenu } from "../context-menu";

SetupMocks.resizeObserver();

const rows = [{ value: "first" }, { value: "second" }];
const columns = [
  { accessorKey: "value", meta: { filterType: "text" as const } },
];

function Harness({ cells }: { cells: Cell<(typeof rows)[number], unknown>[] }) {
  const contextMenuRef = useRef<Cell<(typeof rows)[number], unknown> | null>(
    null,
  );
  const tableRef = useRef<HTMLTableSectionElement>(null);
  const tableBody = (
    <tbody ref={tableRef}>
      {cells.map((cell) => {
        return (
          <tr key={cell.id}>
            <td
              data-cell-id={cell.id}
              onContextMenu={() => {
                contextMenuRef.current = cell;
              }}
            >
              {String(cell.getValue())}
            </td>
          </tr>
        );
      })}
    </tbody>
  );
  return (
    <table>
      <DataTableContextMenu
        contextMenuRef={contextMenuRef}
        tableRef={tableRef}
        tableBody={tableBody}
        copyAllCells={() => undefined}
      />
    </table>
  );
}

it("filters the latest right-clicked cell when the menu is already open", () => {
  const onFilter = vi.fn();
  const table = createTable({
    data: rows,
    columns,
    locale: "en-US",
    getCoreRowModel: getCoreRowModel(),
    onColumnFiltersChange: onFilter,
    state: {},
    onStateChange: () => undefined,
    renderFallbackValue: null,
  });
  render(
    <Harness
      cells={table.getRowModel().rows.map((row) => row.getAllCells()[0])}
    />,
  );

  fireEvent.contextMenu(screen.getByText("first"));
  expect(
    screen.getByRole("menuitem", { name: "Filter by this value" }),
  ).toBeInTheDocument();
  fireEvent.contextMenu(screen.getByText("second"));
  fireEvent.click(
    screen.getByRole("menuitem", { name: "Filter by this value" }),
  );

  const update = onFilter.mock.calls.at(-1)?.[0];
  expect(update([])).toEqual([
    {
      id: "value",
      value: { type: "text", operator: "equals", text: "second" },
    },
  ]);
});
