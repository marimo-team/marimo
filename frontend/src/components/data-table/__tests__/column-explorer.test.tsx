/* Copyright 2026 Marimo. All rights reserved. */

import {
  type ColumnDef,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ColumnExplorerPanel } from "../column-explorer-panel/column-explorer";
import type { FieldTypesWithExternalType } from "../types";

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {};
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
});

const FIELD_TYPES: FieldTypesWithExternalType = [
  ["customer_name", ["string", "str"]],
  ["cust_age", ["integer", "int"]],
  ["order_total", ["number", "float"]],
];

type Row = Record<string, unknown>;

const TEST_COLUMNS: ColumnDef<Row>[] = [
  { id: "customer_name", accessorKey: "customer_name" },
  { id: "cust_age", accessorKey: "cust_age" },
  { id: "order_total", accessorKey: "order_total" },
];

function PanelHarness() {
  const table = useReactTable<Row>({
    data: [],
    columns: TEST_COLUMNS,
    getCoreRowModel: getCoreRowModel(),
    locale: "en-US",
  });
  return (
    <ColumnExplorerPanel
      previewColumn={vi.fn().mockResolvedValue({})}
      fieldTypes={FIELD_TYPES}
      totalRows={3}
      totalColumns={3}
      tableId="t1"
      table={table}
    />
  );
}

function renderPanel() {
  return render(
    <TooltipProvider>
      <PanelHarness />
    </TooltipProvider>,
  );
}

function getSearchInput() {
  return screen.getByPlaceholderText("Search columns...");
}

describe("ColumnExplorerPanel search", () => {
  it("shows all columns when search is empty", () => {
    renderPanel();
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(screen.getByText("cust_age")).toBeInTheDocument();
    expect(screen.getByText("order_total")).toBeInTheDocument();
  });

  it("matches a word prefix against any column word", () => {
    renderPanel();
    fireEvent.change(getSearchInput(), { target: { value: "cust" } });
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(screen.getByText("cust_age")).toBeInTheDocument();
    expect(screen.queryByText("order_total")).not.toBeInTheDocument();
  });

  it("matches multi-word queries across column words in any order", () => {
    renderPanel();
    fireEvent.change(getSearchInput(), { target: { value: "name cust" } });
    expect(screen.getByText("customer_name")).toBeInTheDocument();
    expect(screen.queryByText("cust_age")).not.toBeInTheDocument();
    expect(screen.queryByText("order_total")).not.toBeInTheDocument();
  });

  it("filters out columns that don't match any needle word", () => {
    renderPanel();
    fireEvent.change(getSearchInput(), { target: { value: "xyz" } });
    expect(screen.queryByText("customer_name")).not.toBeInTheDocument();
    expect(screen.queryByText("cust_age")).not.toBeInTheDocument();
    expect(screen.queryByText("order_total")).not.toBeInTheDocument();
  });
});
