/* Copyright 2026 Marimo. All rights reserved. */

import type { Table } from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it } from "vitest";
import { SELECT_COLUMN_ID } from "../../types";
import { useCellSelectionReducerActions } from "../atoms";
import { CellSelectionStats } from "../cell-selection-stats";
import { CellSelectionProvider } from "../provider";
import { createMockCell, createMockRow, createMockTable } from "./test-utils";

function TestHarness({
  table,
  selectedCellIds,
}: {
  table: Table<unknown>;
  selectedCellIds: Set<string>;
}) {
  const actions = useCellSelectionReducerActions();
  useEffect(() => {
    actions.setSelectedCells(selectedCellIds);
  }, [actions, selectedCellIds]);
  return <CellSelectionStats table={table} />;
}

describe("CellSelectionStats", () => {
  it("should return null when fewer than 2 cells are selected", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 10),
      createMockCell("0_1", 20),
    ]);
    const table = createMockTable([row], []);

    const { container } = render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0"])} />
      </CellSelectionProvider>,
    );

    expect(container.firstChild).toBeNull();
  });

  it("should display Count stat when 2 or more cells are selected", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 10),
      createMockCell("0_1", 20),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 2")).toBeInTheDocument();
  });

  it("should display Sum when selection contains numeric values", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 10),
      createMockCell("0_1", 20),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Sum: 30")).toBeInTheDocument();
  });

  it("should display Average when selection contains numeric values", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 10),
      createMockCell("0_1", 20),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Average: 15")).toBeInTheDocument();
  });

  it("should not display Sum or Average when selection has no numeric values", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", "a"),
      createMockCell("0_1", "b"),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 2")).toBeInTheDocument();
    expect(screen.queryByText(/Sum:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Average:/)).not.toBeInTheDocument();
  });

  it("should round sum and average to 8 decimal places", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 0.1122334411),
      createMockCell("0_1", 0.1122334411),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Sum: 0.22446688")).toBeInTheDocument(); // Round 0.2244668866 to 8 decimal places
    expect(screen.getByText("Average: 0.11223344")).toBeInTheDocument(); // Round 0.1122334411 to 8 decimal places
  });

  it("should correctly round sum and average to 8 decimal places", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 0.1122334433),
      createMockCell("0_1", 0.1122334433),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Sum: 0.22446689")).toBeInTheDocument(); // Round 0.2244668866 to 8 decimal places
    expect(screen.getByText("Average: 0.11223344")).toBeInTheDocument(); // Round 0.1122334433 to 8 decimal places
  });

  it("should not add extra decimal places to sum and average", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 0.1),
      createMockCell("0_1", 0.2),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Sum: 0.3")).toBeInTheDocument();
    expect(screen.getByText("Average: 0.15")).toBeInTheDocument();
  });

  it("should not display any stats when exactly one cell is selected", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 10),
      createMockCell("0_1", 20),
    ]);
    const table = createMockTable([row], []);

    const { container } = render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0"])} />
      </CellSelectionProvider>,
    );

    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/Count:/)).not.toBeInTheDocument();
  });

  it("should display Sum and Average for negative numbers", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", -10),
      createMockCell("0_1", -20),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 2")).toBeInTheDocument();
    expect(screen.getByText("Sum: -30")).toBeInTheDocument();
    expect(screen.getByText("Average: -15")).toBeInTheDocument();
  });

  it("should display Sum and Average for number strings", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", "42"),
      createMockCell("0_1", "3.14"),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness table={table} selectedCellIds={new Set(["0_0", "0_1"])} />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 2")).toBeInTheDocument();
    expect(screen.getByText("Sum: 45.14")).toBeInTheDocument();
    expect(screen.getByText("Average: 22.57")).toBeInTheDocument();
  });

  it("should skip NaN and Infinity and show stats for finite values only", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 5),
      createMockCell("0_1", NaN),
      createMockCell("0_2", Infinity),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness
          table={table}
          selectedCellIds={new Set(["0_0", "0_1", "0_2"])}
        />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 3")).toBeInTheDocument();
    expect(screen.getByText("Sum: 5")).toBeInTheDocument();
    expect(screen.getByText("Average: 5")).toBeInTheDocument();
  });

  it("should ignore select checkbox column for Count, Sum and Average", () => {
    const selectCellId = `0_${SELECT_COLUMN_ID}`;
    const row = createMockRow("0", [
      createMockCell(selectCellId, 10),
      createMockCell("0_0", 20),
      createMockCell("0_1", 30),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness
          table={table}
          selectedCellIds={new Set([selectCellId, "0_0", "0_1"])}
        />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 2")).toBeInTheDocument();
    expect(screen.getByText("Sum: 50")).toBeInTheDocument();
    expect(screen.getByText("Average: 25")).toBeInTheDocument();
  });

  it("should not display stats when only checkbox column cells are selected", () => {
    const selectCellId1 = `0_${SELECT_COLUMN_ID}`;
    const selectCellId2 = `1_${SELECT_COLUMN_ID}`;
    const row1 = createMockRow("0", [createMockCell(selectCellId1, true)]);
    const row2 = createMockRow("1", [createMockCell(selectCellId2, false)]);
    const table = createMockTable([row1, row2], []);

    const { container } = render(
      <CellSelectionProvider>
        <TestHarness
          table={table}
          selectedCellIds={new Set([selectCellId1, selectCellId2])}
        />
      </CellSelectionProvider>,
    );

    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/Count:/)).not.toBeInTheDocument();
  });

  it("should show Sum and Average only for numeric cells when selection has mixed types", () => {
    const row = createMockRow("0", [
      createMockCell("0_0", 10),
      createMockCell("0_1", "abc"),
      createMockCell("0_2", undefined),
    ]);
    const table = createMockTable([row], []);

    render(
      <CellSelectionProvider>
        <TestHarness
          table={table}
          selectedCellIds={new Set(["0_0", "0_1", "0_2"])}
        />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 3")).toBeInTheDocument();
    expect(screen.getByText("Sum: 10")).toBeInTheDocument();
    expect(screen.getByText("Average: 10")).toBeInTheDocument();
  });

  it("should display stats for multiple numeric cells across rows", () => {
    const row1 = createMockRow("0", [
      createMockCell("0_0", 1),
      createMockCell("0_1", 2),
    ]);
    const row2 = createMockRow("1", [
      createMockCell("1_0", 3),
      createMockCell("1_1", 4),
    ]);
    const table = createMockTable([row1, row2], []);

    render(
      <CellSelectionProvider>
        <TestHarness
          table={table}
          selectedCellIds={new Set(["0_0", "0_1", "1_0", "1_1"])}
        />
      </CellSelectionProvider>,
    );

    expect(screen.getByText("Count: 4")).toBeInTheDocument();
    expect(screen.getByText("Sum: 10")).toBeInTheDocument();
    expect(screen.getByText("Average: 2.5")).toBeInTheDocument();
  });
});
