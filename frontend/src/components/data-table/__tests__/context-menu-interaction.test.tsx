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

function createCells() {
  const table = createTable({
    data: rows,
    columns,
    locale: "en-US",
    getCoreRowModel: getCoreRowModel(),
    onColumnFiltersChange: () => undefined,
    state: {},
    onStateChange: () => undefined,
    renderFallbackValue: null,
  });
  return table.getRowModel().rows.map((row) => row.getAllCells()[0]);
}

function Harness({ cells }: { cells: Cell<(typeof rows)[number], unknown>[] }) {
  const contextMenuRef = useRef<Cell<(typeof rows)[number], unknown> | null>(
    null,
  );
  const tableRef = useRef<HTMLTableSectionElement>(null);
  const tableBody = (
    <tbody ref={tableRef}>
      <tr>
        <td>empty</td>
      </tr>
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

  const firstCell = screen.getByText("first");
  const secondCell = screen.getByText("second");
  fireEvent.contextMenu(firstCell);
  expect(firstCell).toHaveClass("bg-(--green-4)");
  expect(
    screen.getByRole("menuitem", { name: "Filter by this value" }),
  ).toBeInTheDocument();
  fireEvent.contextMenu(secondCell);
  expect(firstCell).not.toHaveClass("bg-(--green-4)");
  expect(secondCell).toHaveClass("bg-(--green-4)");
  fireEvent.click(
    screen.getByRole("menuitem", { name: "Filter by this value" }),
  );
  expect(firstCell).not.toHaveClass("bg-(--green-4)");
  expect(secondCell).not.toHaveClass("bg-(--green-4)");

  const update = onFilter.mock.calls.at(-1)?.[0];
  expect(update([])).toEqual([
    {
      id: "value",
      value: { type: "text", operator: "equals", text: "second" },
    },
  ]);
});

it("does not reuse a previous cell after the menu closes", () => {
  render(<Harness cells={createCells()} />);

  const firstCell = screen.getByText("first");
  fireEvent.contextMenu(firstCell);
  expect(firstCell).toHaveClass("bg-(--green-4)");
  fireEvent.keyDown(document.activeElement ?? document.body, {
    key: "Escape",
  });
  expect(firstCell).not.toHaveClass("bg-(--green-4)");
  expect(screen.queryByRole("menu")).not.toBeInTheDocument();

  // Right-clicking outside any data cell must not resurrect the old one
  fireEvent.contextMenu(screen.getByText("empty"));
  expect(firstCell).not.toHaveClass("bg-(--green-4)");
  expect(
    screen.queryByRole("menuitem", { name: "Filter by this value" }),
  ).not.toBeInTheDocument();
});
