/* Copyright 2026 Marimo. All rights reserved. */
import type { Column, Table } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { FilterPillEditor } from "../filter-pill-editor";
import { Filter } from "../filters";

const renderWithProviders = (ui: React.ReactElement) =>
  render(<TooltipProvider>{ui}</TooltipProvider>);

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {
    // jsdom does not implement scrollIntoView; cmdk calls it on selection.
  };
  // jsdom lacks hasPointerCapture used by radix Select
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!global.HTMLElement.prototype.scrollTo) {
    global.HTMLElement.prototype.scrollTo = () => {
      // noop for jsdom
    };
  }
});

function makeColumn(
  id: string,
  filterType:
    | "text"
    | "number"
    | "boolean"
    | "select"
    | "date"
    | "datetime"
    | "time",
): Column<unknown, unknown> {
  return {
    id,
    columnDef: { meta: { filterType, dataType: "string" } },
  } as unknown as Column<unknown, unknown>;
}

function mockTable(): Table<unknown> {
  const columns = [
    makeColumn("name", "text"),
    makeColumn("age", "number"),
    makeColumn("when", "date"),
    makeColumn("at", "datetime"),
    makeColumn("clock", "time"),
  ];
  return {
    getAllColumns: () => columns,
    getColumn: (id: string) => columns.find((c) => c.id === id),
    setColumnFilters: vi.fn(),
  } as unknown as Table<unknown>;
}

async function calculateTopK() {
  return {
    data: [
      ["alice", 3],
      ["bob", 1],
    ] as Array<[string, number]>,
  };
}

describe("FilterPillEditor — snapshot rehydration", () => {
  it("rehydrates a number > snapshot with seeded value", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "age",
          value: Filter.number({ operator: ">", value: 18 }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue("18")).toBeInTheDocument();
    expect(screen.getByLabelText("value")).toBeInTheDocument();
    // No min/max range fields rendered for comparison operator.
    expect(screen.queryByLabelText("min")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("max")).not.toBeInTheDocument();
  });

  it("rehydrates a number between snapshot with seeded min/max", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "age",
          value: Filter.number({ operator: "between", min: 1, max: 9 }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue("1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("9")).toBeInTheDocument();
  });

  it("rehydrates a text in snapshot seeding the creatable picker", async () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "name",
          value: Filter.text({ operator: "in", values: ["a", "b"] }),
        }}
        table={mockTable()}
        calculateTopKRows={calculateTopK}
        onClose={vi.fn()}
      />,
    );
    expect(await screen.findByText("[a, b]")).toBeInTheDocument();
  });

  it("rehydrates a text contains snapshot with seeded text", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "name",
          value: Filter.text({ operator: "contains", text: "hello" }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByDisplayValue("hello")).toBeInTheDocument();
  });

  it("hides the value slot for is_null/is_not_null/is_empty", () => {
    const { rerender } = renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "name",
          value: Filter.text({ operator: "is_null" }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByText("Value")).not.toBeInTheDocument();

    rerender(
      <TooltipProvider>
        <FilterPillEditor
          snapshot={{
            columnId: "name",
            value: Filter.text({ operator: "is_empty" }),
          }}
          table={mockTable()}
          onClose={vi.fn()}
        />
      </TooltipProvider>,
    );
    expect(screen.queryByText("Value")).not.toBeInTheDocument();
  });
});

describe("FilterPillEditor — date/datetime/time", () => {
  it("rehydrates a date between snapshot with the range picker", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "when",
          value: Filter.date({
            operator: "between",
            min: new Date("2024-01-01T00:00:00Z"),
            max: new Date("2024-06-01T00:00:00Z"),
          }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("range")).toBeInTheDocument();
    expect(screen.queryByLabelText("value")).not.toBeInTheDocument();
  });

  it("rehydrates a datetime <= snapshot with a single value picker", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "at",
          value: Filter.datetime({
            operator: "<=",
            value: new Date("2024-06-01T12:00:00Z"),
          }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("value")).toBeInTheDocument();
    expect(screen.queryByLabelText("range")).not.toBeInTheDocument();
  });

  it("renders min/max TimeFields for time between", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "clock",
          value: Filter.time({
            operator: "between",
            min: new Date("2024-01-01T08:00:00Z"),
            max: new Date("2024-01-01T17:00:00Z"),
          }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("min")).toBeInTheDocument();
    expect(screen.getByLabelText("max")).toBeInTheDocument();
  });

  it("hides the value slot for date is_null", () => {
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "when",
          value: Filter.date({ operator: "is_null" }),
        }}
        table={mockTable()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByText("Value")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("range")).not.toBeInTheDocument();
  });
});

describe("FilterPillEditor — apply", () => {
  it("commits a number > filter via setColumnFilters", () => {
    const table = mockTable();
    const onClose = vi.fn();
    renderWithProviders(
      <FilterPillEditor
        snapshot={{
          columnId: "age",
          value: Filter.number({ operator: ">", value: 18 }),
        }}
        table={table}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByLabelText("Apply filter"));
    expect(table.setColumnFilters).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);

    const updater = (table.setColumnFilters as ReturnType<typeof vi.fn>).mock
      .calls[0][0];
    const next = updater([]);
    expect(next).toEqual([
      {
        id: "age",
        value: { type: "number", operator: ">", value: 18 },
      },
    ]);
  });
});
