/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { GetRowResult } from "@/plugins/impl/DataTablePlugin";
import type { FieldTypesWithExternalType } from "../../types";
import { RowViewerPanel } from "../row-viewer";

const renderWithProviders = (component: React.ReactNode) => {
  return render(
    <TooltipProvider>
      <Provider>{component}</Provider>
    </TooltipProvider>,
  );
};

describe("RowExpandedPanel", () => {
  it("preserves Space activation on navigation buttons", async () => {
    const select = vi.fn();
    const navigate = vi.fn();
    renderWithProviders(
      <RowViewerPanel
        rowIdx={0}
        setRowIdx={navigate}
        totalRows={2}
        fieldTypes={[["name", ["string", "string"]]]}
        getRow={async () => ({ rows: [{ name: "Alice" }] })}
        isSelectable={true}
        isRowSelected={false}
        handleRowSelectionChange={select}
      />,
    );
    await screen.findByText("Alice");
    const next = screen.getByRole("button", { name: "Next row" });
    expect(fireEvent.keyDown(next, { key: " " })).toBe(true);
    expect(select).not.toHaveBeenCalled();
    fireEvent.click(next);
    expect(navigate).toHaveBeenCalledExactlyOnceWith(1);
  });

  const mockFieldTypes: FieldTypesWithExternalType = [
    ["name", ["string", "string"]],
    ["age", ["number", "number"]],
  ];

  const mockGetRow = vi
    .fn()
    .mockImplementation((rowIdx: number): Promise<GetRowResult> => {
      const mockData = [
        { name: "John", age: 30 },
        { name: "Jane", age: 25 },
        { name: "Alice", age: 35 },
      ];
      return Promise.resolve({ rows: [mockData[rowIdx]] });
    });

  const mockSetRowIdx = vi.fn();

  it("renders data in row viewer panel", async () => {
    renderWithProviders(
      <RowViewerPanel
        rowIdx={0}
        setRowIdx={mockSetRowIdx}
        totalRows={3}
        fieldTypes={mockFieldTypes}
        getRow={mockGetRow}
        isSelectable={true}
        isRowSelected={false}
        handleRowSelectionChange={() => {
          // NO-OP
        }}
      />,
    );

    // Wait for the data to load
    expect(await screen.findByText("John")).toBeInTheDocument();
    expect(await screen.findByText("30")).toBeInTheDocument();
  });

  it("renders pandas timedelta NaT as a sentinel", async () => {
    renderWithProviders(
      <RowViewerPanel
        rowIdx={0}
        setRowIdx={mockSetRowIdx}
        totalRows={1}
        fieldTypes={[["duration", ["string", "timedelta64[us]"]]]}
        getRow={async () => ({ rows: [{ duration: "NaT" }] })}
        isSelectable={false}
        isRowSelected={false}
      />,
    );

    expect(await screen.findByLabelText("Not a Time")).toBeInTheDocument();
  });
});
