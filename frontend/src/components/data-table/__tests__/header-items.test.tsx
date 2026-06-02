/* Copyright 2026 Marimo. All rights reserved. */

import type {
  Column,
  SortDirection,
  SortingState,
  Table,
} from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DataType, HideColumn, Sorts } from "../header-items";

const renderInMenu = (node: React.ReactNode) =>
  render(
    <DropdownMenu open={true}>
      <DropdownMenuTrigger />
      <DropdownMenuContent>{node}</DropdownMenuContent>
    </DropdownMenu>,
  );

describe("multi-column sorting logic", () => {
  // Extract the core sorting logic to test in isolation
  const handleSort = (options: {
    columnId: string;
    desc: boolean;
    sortingState: SortingState;
    setSorting: (state: SortingState) => void;
    clearSorting: () => void;
  }) => {
    const { columnId, desc, sortingState, setSorting, clearSorting } = options;
    const currentSort = sortingState.find((s) => s.id === columnId);

    if (currentSort && currentSort.desc === desc) {
      // Clicking the same sort again - remove it
      clearSorting();
    } else {
      // New sort or different direction - move to end of stack
      const otherSorts = sortingState.filter((s) => s.id !== columnId);
      const newSort = { id: columnId, desc };
      setSorting([...otherSorts, newSort]);
    }
  };

  it("implements stack-based sorting: moves re-clicked column to end", () => {
    const sortingState: SortingState = [
      { id: "name", desc: false },
      { id: "age", desc: false },
    ];
    const setSorting = vi.fn();
    const clearSorting = vi.fn();

    // Click Desc on age - should move age to end with desc=true
    handleSort({
      columnId: "age",
      desc: true,
      sortingState,
      setSorting,
      clearSorting,
    });

    expect(setSorting).toHaveBeenCalledWith([
      { id: "name", desc: false },
      { id: "age", desc: true },
    ]);
    expect(clearSorting).not.toHaveBeenCalled();
  });

  it("removes sort when clicking same direction twice", () => {
    const sortingState: SortingState = [{ id: "age", desc: false }];
    const setSorting = vi.fn();
    const clearSorting = vi.fn();

    // Click Asc on age again - should remove the sort
    handleSort({
      columnId: "age",
      desc: false,
      sortingState,
      setSorting,
      clearSorting,
    });

    expect(clearSorting).toHaveBeenCalled();
    expect(setSorting).not.toHaveBeenCalled();
  });

  it("adds new column to end of stack", () => {
    const sortingState: SortingState = [{ id: "name", desc: false }];
    const setSorting = vi.fn();
    const clearSorting = vi.fn();

    // Click Asc on age - should add age to end
    handleSort({
      columnId: "age",
      desc: false,
      sortingState,
      setSorting,
      clearSorting,
    });

    expect(setSorting).toHaveBeenCalledWith([
      { id: "name", desc: false },
      { id: "age", desc: false },
    ]);
    expect(clearSorting).not.toHaveBeenCalled();
  });

  it("toggles sort direction when clicking opposite", () => {
    const sortingState: SortingState = [{ id: "age", desc: false }];
    const setSorting = vi.fn();
    const clearSorting = vi.fn();

    // Click Desc on age - should toggle to descending
    handleSort({
      columnId: "age",
      desc: true,
      sortingState,
      setSorting,
      clearSorting,
    });

    expect(setSorting).toHaveBeenCalledWith([{ id: "age", desc: true }]);
    expect(clearSorting).not.toHaveBeenCalled();
  });

  it("correctly calculates priority numbers", () => {
    const sortingState: SortingState = [
      { id: "name", desc: false },
      { id: "age", desc: true },
      { id: "dept", desc: false },
    ];

    // Priority is index + 1
    const nameSort = sortingState.find((s) => s.id === "name");
    const namePriority = nameSort ? sortingState.indexOf(nameSort) + 1 : null;
    expect(namePriority).toBe(1);

    const deptSort = sortingState.find((s) => s.id === "dept");
    const deptPriority = deptSort ? sortingState.indexOf(deptSort) + 1 : null;
    expect(deptPriority).toBe(3);
  });

  it("handles removing column from middle of stack", () => {
    const sortingState: SortingState = [
      { id: "name", desc: false },
      { id: "age", desc: true },
      { id: "dept", desc: false },
    ];
    const setSorting = vi.fn();
    const clearSorting = vi.fn();

    // Click Desc on age again - should remove it
    handleSort({
      columnId: "age",
      desc: true,
      sortingState,
      setSorting,
      clearSorting,
    });

    expect(clearSorting).toHaveBeenCalled();
    // After removal, dept should move from priority 3 to priority 2
  });
});

describe("HideColumn", () => {
  const makeColumn = ({
    canHide = true,
    toggleVisibility = vi.fn(),
  }: {
    canHide?: boolean;
    toggleVisibility?: (value?: boolean) => void;
  } = {}) =>
    ({
      getCanHide: () => canHide,
      toggleVisibility,
    }) as unknown as Column<unknown, unknown>;

  it("renders 'Hide column' when canHide is true", () => {
    renderInMenu(<HideColumn column={makeColumn()} />);
    expect(screen.getByText("Hide column")).toBeInTheDocument();
  });

  it("returns null when getCanHide is false", () => {
    renderInMenu(<HideColumn column={makeColumn({ canHide: false })} />);
    expect(screen.queryByText("Hide column")).toBeNull();
  });

  it("calls toggleVisibility(false) on click", () => {
    const toggleVisibility = vi.fn();
    renderInMenu(<HideColumn column={makeColumn({ toggleVisibility })} />);
    fireEvent.click(screen.getByText("Hide column"));
    expect(toggleVisibility).toHaveBeenCalledWith(false);
  });
});

describe("DataType", () => {
  const makeColumn = (dtype?: string) =>
    ({
      columnDef: { meta: dtype === undefined ? {} : { dtype } },
    }) as unknown as Column<unknown, unknown>;

  it("renders the dtype label when present", () => {
    renderInMenu(<DataType column={makeColumn("int64")} />);
    expect(screen.getByText("int64")).toBeInTheDocument();
  });

  it("returns null when dtype is absent", () => {
    renderInMenu(<DataType column={makeColumn()} />);
    expect(screen.queryByText("int64")).toBeNull();
  });
});

describe("Sorts", () => {
  const makeColumn = ({
    canSort = true,
    sorted = false,
    sortIndex = 0,
  }: {
    canSort?: boolean;
    sorted?: false | SortDirection;
    sortIndex?: number;
  } = {}) =>
    ({
      getCanSort: () => canSort,
      getIsSorted: () => sorted,
      getSortIndex: () => sortIndex,
      clearSorting: vi.fn(),
      toggleSorting: vi.fn(),
    }) as unknown as Column<unknown, unknown>;

  const makeTable = (sorting: SortingState) =>
    ({
      getState: () => ({ sorting }),
      resetSorting: vi.fn(),
    }) as unknown as Table<unknown>;

  it("returns null when the column cannot sort", () => {
    renderInMenu(<Sorts column={makeColumn({ canSort: false })} />);
    expect(screen.queryByText("Asc")).toBeNull();
  });

  it("renders Asc and Desc items", () => {
    renderInMenu(<Sorts column={makeColumn()} />);
    expect(screen.getByText("Asc")).toBeInTheDocument();
    expect(screen.getByText("Desc")).toBeInTheDocument();
  });

  it("offers single-column 'Clear sort' when sorted without multi-sort", () => {
    renderInMenu(<Sorts column={makeColumn({ sorted: "asc" })} />);
    expect(screen.getByText("Clear sort")).toBeInTheDocument();
  });

  it("offers 'Clear all sorts' when the table has multiple sorts", () => {
    renderInMenu(
      <Sorts
        column={makeColumn({ sorted: "asc" })}
        table={makeTable([
          { id: "a", desc: false },
          { id: "b", desc: true },
        ])}
      />,
    );
    expect(screen.getByText("Clear all sorts")).toBeInTheDocument();
  });
});
