/* Copyright 2026 Marimo. All rights reserved. */
import type { ColumnFiltersState } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AddFilterButton } from "../add-filter-button";
import { FilterPills } from "../filter-pills";
import { buildEditorSnapshot } from "../filter-pill-editor";
import { Filter, type Snapshot } from "../filters";
import {
  buildFilterTestTable,
  type FilterColumnSpec,
} from "./filter-test-utils";

const renderWithProviders = (ui: React.ReactElement) =>
  render(<TooltipProvider>{ui}</TooltipProvider>);

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {
    // jsdom does not implement scrollIntoView; cmdk calls it on selection.
  };
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!global.HTMLElement.prototype.scrollTo) {
    global.HTMLElement.prototype.scrollTo = () => {
      // noop for jsdom
    };
  }
});

const DEFAULT_COLUMNS: FilterColumnSpec[] = [
  { id: "name", filterType: "text" },
  { id: "age", filterType: "number" },
  { id: "when", filterType: "date" },
];

const mockTable = (specs: FilterColumnSpec[] = DEFAULT_COLUMNS) =>
  buildFilterTestTable(specs).table;

describe("FilterPills — strip gating", () => {
  it("renders nothing when there are no filters and no pending add-snapshot", () => {
    const { container } = renderWithProviders(
      <FilterPills
        filters={[]}
        table={mockTable()}
        addFilterSnapshot={null}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders the strip and + button when at least one filter exists", () => {
    const filters: ColumnFiltersState = [
      {
        id: "age",
        value: Filter.number({ operator: ">", value: 18 }),
      },
    ];
    renderWithProviders(
      <FilterPills
        filters={filters}
        table={mockTable()}
        addFilterSnapshot={null}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Add filter")).toBeInTheDocument();
    expect(screen.getByLabelText("Edit filter on age")).toBeInTheDocument();
  });

  it("mounts the strip with no filters when a pending add-snapshot is set", () => {
    const table = mockTable();
    const snapshot: Snapshot = buildEditorSnapshot(table.getAllColumns()[0]);
    renderWithProviders(
      <FilterPills
        filters={[]}
        table={table}
        addFilterSnapshot={snapshot}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Add filter")).toBeInTheDocument();
  });
});

describe("AddFilterButton", () => {
  it("does not render when there are no editable columns", () => {
    const table = mockTable([{ id: "opaque" }]);
    const { container } = renderWithProviders(
      <AddFilterButton
        table={table}
        snapshot={null}
        onSnapshotChange={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("seeds the editor with the first editable column's dtype default on click", () => {
    const table = mockTable();
    const onSnapshotChange = vi.fn();
    renderWithProviders(
      <AddFilterButton
        table={table}
        snapshot={null}
        onSnapshotChange={onSnapshotChange}
      />,
    );
    fireEvent.click(screen.getByLabelText("Add filter"));
    expect(onSnapshotChange).toHaveBeenCalledTimes(1);
    expect(onSnapshotChange).toHaveBeenCalledWith({
      columnId: "name",
      value: { type: "text", operator: "contains" },
    });
  });

  it("clears the snapshot when the popover closes", () => {
    const onSnapshotChange = vi.fn();
    const snapshot: Snapshot = {
      columnId: "age",
      value: Filter.number({ operator: ">", value: 5 }),
    };
    renderWithProviders(
      <AddFilterButton
        table={mockTable()}
        snapshot={snapshot}
        onSnapshotChange={onSnapshotChange}
      />,
    );
    // Pressing Escape closes the popover via radix.
    fireEvent.keyDown(document.body, { key: "Escape" });
    expect(onSnapshotChange).toHaveBeenCalledWith(null);
  });

  it("renders the editor when a snapshot is provided", () => {
    renderWithProviders(
      <AddFilterButton
        table={mockTable()}
        snapshot={{
          columnId: "age",
          value: Filter.number({ operator: ">", value: 7 }),
        }}
        onSnapshotChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Apply filter")).toBeInTheDocument();
    expect(screen.getByDisplayValue("7")).toBeInTheDocument();
  });
});

describe("FilterPills — pill edit", () => {
  it("opens the editor with the pill's snapshot when clicked", () => {
    const filters: ColumnFiltersState = [
      {
        id: "age",
        value: Filter.number({ operator: ">", value: 42 }),
      },
    ];
    renderWithProviders(
      <FilterPills
        filters={filters}
        table={mockTable()}
        addFilterSnapshot={null}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Edit filter on age"));
    expect(screen.getByLabelText("Apply filter")).toBeInTheDocument();
    expect(screen.getByDisplayValue("42")).toBeInTheDocument();
  });

  it("splices in place via editIndex when applying an edit", () => {
    const { table, setColumnFilters } = buildFilterTestTable(DEFAULT_COLUMNS);
    const filters: ColumnFiltersState = [
      {
        id: "name",
        value: Filter.text({ operator: "contains", text: "foo" }),
      },
      {
        id: "age",
        value: Filter.number({ operator: ">", value: 1 }),
      },
    ];
    renderWithProviders(
      <FilterPills
        filters={filters}
        table={table}
        addFilterSnapshot={null}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Edit filter on age"));
    fireEvent.click(screen.getByLabelText("Apply filter"));

    const updater = setColumnFilters.mock.calls[0][0];
    const next = updater(filters);
    expect(next).toHaveLength(2);
    expect(next[0].id).toBe("name");
    expect(next[1]).toEqual({
      id: "age",
      value: { type: "number", operator: ">", value: 1 },
    });
  });
});

describe("FilterPills — column-header trigger integration", () => {
  it("opens the editor under the + button with a column-header-supplied snapshot", () => {
    // Simulates what DataTable does when column-header calls
    // requestAddFilter({ columnId: "name" }): it computes a snapshot via
    // buildEditorSnapshot and passes it down as addFilterSnapshot.
    const table = mockTable();
    const snapshot = buildEditorSnapshot(table.getColumn("name")!);
    renderWithProviders(
      <FilterPills
        filters={[]}
        table={table}
        addFilterSnapshot={snapshot}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Apply filter")).toBeInTheDocument();
    // Default text operator is "contains" — the text input renders.
    expect(screen.getByPlaceholderText("Text…")).toBeInTheDocument();
  });

  it("pre-selects 'in' operator when column-header 'Filter by values' is used", () => {
    const table = mockTable();
    const snapshot = buildEditorSnapshot(table.getColumn("name")!, {
      operator: "in",
    });
    renderWithProviders(
      <FilterPills
        filters={[]}
        table={table}
        addFilterSnapshot={snapshot}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    expect(snapshot.value).toEqual({
      type: "text",
      operator: "in",
      values: [],
    });
    expect(screen.getByLabelText("Apply filter")).toBeInTheDocument();
  });
});

describe("FilterPills — overflow", () => {
  it("does not render the 'See all' button when there is no overflow", () => {
    const filters: ColumnFiltersState = [
      { id: "age", value: Filter.number({ operator: ">", value: 5 }) },
    ];
    renderWithProviders(
      <FilterPills
        filters={filters}
        table={mockTable()}
        addFilterSnapshot={null}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText("See all filters")).toBeNull();
  });
});

describe("FilterPill — value truncation", () => {
  it("renders the value with truncation classes inside a tooltip trigger", () => {
    const filters: ColumnFiltersState = [
      {
        id: "name",
        value: Filter.text({ operator: "contains", text: "x".repeat(100) }),
      },
    ];
    renderWithProviders(
      <FilterPills
        filters={filters}
        table={mockTable()}
        addFilterSnapshot={null}
        onAddFilterSnapshotChange={vi.fn()}
      />,
    );
    const valueSpan = screen.getByText(/^"x{100}"$/);
    expect(valueSpan.className).toMatch(/overflow-hidden/);
    expect(valueSpan.className).toMatch(/text-ellipsis/);
  });
});
