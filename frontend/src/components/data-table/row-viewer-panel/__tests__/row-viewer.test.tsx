/* Copyright 2024 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
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
});
