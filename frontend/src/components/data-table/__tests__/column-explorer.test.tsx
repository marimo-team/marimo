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

interface HarnessProps {
  totalColumns?: number;
  initiallyHidden?: string[];
}

function PanelHarness({
  totalColumns = 3,
  initiallyHidden = [],
}: HarnessProps) {
  const table = useReactTable<Row>({
    data: [],
    columns: TEST_COLUMNS,
    getCoreRowModel: getCoreRowModel(),
    locale: "en-US",
    state: {
      columnVisibility: Object.fromEntries(
        initiallyHidden.map((id) => [id, false]),
      ),
    },
  });
  return (
    <ColumnExplorerPanel
      previewColumn={vi.fn().mockResolvedValue({})}
      fieldTypes={FIELD_TYPES}
      totalRows={3}
      totalColumns={totalColumns}
      tableId="t1"
      table={table}
    />
  );
}

function renderPanel(props?: HarnessProps) {
  return render(
    <TooltipProvider>
      <PanelHarness {...(props ?? {})} />
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

describe("ColumnExplorerPanel header counts", () => {
  it("uses rendered-subset total when a clipped column is hidden", () => {
    // Dataset has 100 columns server-side; only 3 are rendered into the
    // TanStack table (the clipped subset). Hiding one of the rendered columns
    // must report "2 visible (1 hidden)", not "99 visible (1 hidden)".
    renderPanel({ totalColumns: 100, initiallyHidden: ["cust_age"] });
    expect(screen.getByText(/2 visible/)).toBeInTheDocument();
    expect(screen.getByText(/\(1 hidden\)/)).toBeInTheDocument();
    expect(screen.queryByText(/99 visible/)).not.toBeInTheDocument();
  });

  it("uses dataset-wide total when no column is hidden", () => {
    renderPanel({ totalColumns: 100 });
    expect(screen.getByText(/100 columns/)).toBeInTheDocument();
    expect(screen.queryByText(/hidden/)).not.toBeInTheDocument();
  });
});

describe("ColumnExplorerPanel visibility actions", () => {
  const showAll = () => screen.getByRole("button", { name: /Show all/ });
  const hideAll = () => screen.getByRole("button", { name: /Hide all/ });

  it("disables 'Show all' when every column is visible", () => {
    renderPanel();
    expect(showAll()).toBeDisabled();
    expect(hideAll()).toBeEnabled();
  });

  it("disables 'Hide all' when every column is hidden", () => {
    renderPanel({
      initiallyHidden: ["customer_name", "cust_age", "order_total"],
    });
    expect(showAll()).toBeEnabled();
    expect(hideAll()).toBeDisabled();
  });

  it("enables both actions when some columns are hidden", () => {
    renderPanel({ initiallyHidden: ["cust_age"] });
    expect(showAll()).toBeEnabled();
    expect(hideAll()).toBeEnabled();
  });
});
