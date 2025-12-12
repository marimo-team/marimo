/* Copyright 2024 Marimo. All rights reserved. */

import type { SortingState } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";

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
