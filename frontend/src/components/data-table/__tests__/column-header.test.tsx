/* Copyright 2026 Marimo. All rights reserved. */
import type { Column } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DataTableColumnHeader } from "../column-header";
import {
  type AddFilterRequest,
  FilterEditorProvider,
} from "../filter-editor-context";
import { buildFilterTestTable } from "./filter-test-utils";

beforeAll(() => {
  global.HTMLElement.prototype.scrollIntoView = () => {
    // jsdom does not implement scrollIntoView
  };
  if (!global.HTMLElement.prototype.hasPointerCapture) {
    global.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!global.HTMLElement.prototype.releasePointerCapture) {
    global.HTMLElement.prototype.releasePointerCapture = () => {
      // noop for jsdom
    };
  }
});

function renderHeader(opts: {
  column: Column<unknown, unknown>;
  requestAddFilter?: (req: AddFilterRequest) => void;
  withProvider: boolean;
}) {
  const { column, requestAddFilter, withProvider } = opts;
  const headerNode = (
    <DataTableColumnHeader column={column} header={column.id} />
  );
  return render(
    <TooltipProvider>
      {withProvider ? (
        <FilterEditorProvider
          value={{ requestAddFilter: requestAddFilter ?? vi.fn() }}
        >
          {headerNode}
        </FilterEditorProvider>
      ) : (
        headerNode
      )}
    </TooltipProvider>,
  );
}

const openMenu = () => {
  const trigger = screen.getByLabelText("Column options");
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "Enter" });
};

describe("DataTableColumnHeader — filter menu", () => {
  it("renders Filter and Filter-by-values items for text columns inside a provider", () => {
    const { table } = buildFilterTestTable([
      { id: "name", filterType: "text" },
    ]);
    renderHeader({ column: table.getColumn("name")!, withProvider: true });
    openMenu();
    expect(screen.getByText("Filter")).toBeInTheDocument();
    expect(screen.getByText("Filter by values")).toBeInTheDocument();
  });

  it("renders Filter and Filter-by-values items for number columns", () => {
    const { table } = buildFilterTestTable([
      { id: "age", filterType: "number" },
    ]);
    renderHeader({ column: table.getColumn("age")!, withProvider: true });
    openMenu();
    expect(screen.getByText("Filter")).toBeInTheDocument();
    expect(screen.getByText("Filter by values")).toBeInTheDocument();
  });

  it.each(["date", "datetime", "time", "boolean"] as const)(
    "hides Filter-by-values for %s columns",
    (filterType) => {
      const { table } = buildFilterTestTable([{ id: "col", filterType }]);
      renderHeader({ column: table.getColumn("col")!, withProvider: true });
      openMenu();
      expect(screen.getByText("Filter")).toBeInTheDocument();
      expect(screen.queryByText("Filter by values")).not.toBeInTheDocument();
    },
  );

  it("hides both items when filterType is missing", () => {
    const { table } = buildFilterTestTable([{ id: "opaque" }]);
    renderHeader({ column: table.getColumn("opaque")!, withProvider: true });
    openMenu();
    expect(screen.queryByText("Filter")).not.toBeInTheDocument();
    expect(screen.queryByText("Filter by values")).not.toBeInTheDocument();
  });

  it("hides both items when no FilterEditorProvider is present", () => {
    const { table } = buildFilterTestTable([
      { id: "name", filterType: "text" },
    ]);
    renderHeader({ column: table.getColumn("name")!, withProvider: false });
    openMenu();
    expect(screen.queryByText("Filter")).not.toBeInTheDocument();
    expect(screen.queryByText("Filter by values")).not.toBeInTheDocument();
  });

  it("invokes requestAddFilter with columnId when Filter is clicked", () => {
    const requestAddFilter = vi.fn();
    const { table } = buildFilterTestTable([
      { id: "name", filterType: "text" },
    ]);
    renderHeader({
      column: table.getColumn("name")!,
      requestAddFilter,
      withProvider: true,
    });
    openMenu();
    fireEvent.click(screen.getByText("Filter"));
    expect(requestAddFilter).toHaveBeenCalledTimes(1);
    expect(requestAddFilter).toHaveBeenCalledWith({ columnId: "name" });
  });

  it("invokes requestAddFilter with operator='in' when Filter by values is clicked", () => {
    const requestAddFilter = vi.fn();
    const { table } = buildFilterTestTable([
      { id: "name", filterType: "text" },
    ]);
    renderHeader({
      column: table.getColumn("name")!,
      requestAddFilter,
      withProvider: true,
    });
    openMenu();
    fireEvent.click(screen.getByText("Filter by values"));
    expect(requestAddFilter).toHaveBeenCalledTimes(1);
    expect(requestAddFilter).toHaveBeenCalledWith({
      columnId: "name",
      operator: "in",
    });
  });
});
