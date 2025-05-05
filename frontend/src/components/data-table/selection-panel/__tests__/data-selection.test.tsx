/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { DataSelectionPanel } from "../data-selection";
import type { Row } from "@tanstack/react-table";
import { Provider } from "jotai";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PanelGroup } from "react-resizable-panels";

const renderWithProviders = (component: React.ReactNode) => {
  return render(
    <TooltipProvider>
      <Provider>{component}</Provider>
    </TooltipProvider>,
  );
};

describe("DataSelectionPanel", () => {
  const mockRows = [
    {
      getAllCells: () => [
        {
          column: { id: "name", columnDef: { meta: { dataType: "string" } } },
          getValue: () => "John",
          renderValue: () => "John",
        },
        {
          column: { id: "age", columnDef: { meta: { dataType: "number" } } },
          getValue: () => 30,
          renderValue: () => "30",
        },
      ],
    },
  ] as Array<Row<unknown>>;

  const mockClosePanel = vi.fn();

  it("renders data in selection panel", () => {
    renderWithProviders(
      <DataSelectionPanel rows={mockRows} closePanel={mockClosePanel} />,
    );

    expect(screen.getByText("John")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
  });

  it("renders in overlay mode when isOverlay is true", () => {
    renderWithProviders(
      <PanelGroup direction="horizontal">
        <DataSelectionPanel rows={mockRows} closePanel={mockClosePanel} />
      </PanelGroup>,
    );

    const overlayButton = screen.getByRole("button", {
      name: /turn off overlay/i,
    });
    fireEvent.click(overlayButton);

    // Check if the panel is rendered with overlay styles
    expect(
      screen.getByRole("button", { name: /overlay content/i }),
    ).toBeInTheDocument();
  });

  it("calls closePanel when close button is clicked", () => {
    renderWithProviders(
      <DataSelectionPanel rows={mockRows} closePanel={mockClosePanel} />,
    );

    const closeButton = screen.getByRole("button", {
      name: /close selection panel/i,
    });
    fireEvent.click(closeButton);

    expect(mockClosePanel).toHaveBeenCalled();
  });
});

describe("DataSelection", () => {
  const JOHNS_AGE = 30;
  const mockRows = [
    {
      getAllCells: () => [
        {
          column: { id: "name", columnDef: { meta: { dataType: "string" } } },
          getValue: () => "John",
          renderValue: () => "John",
        },
        {
          column: { id: "age", columnDef: { meta: { dataType: "number" } } },
          getValue: () => JOHNS_AGE,
          renderValue: () => JOHNS_AGE.toString(),
        },
      ],
    },
    {
      getAllCells: () => [
        {
          column: { id: "name", columnDef: { meta: { dataType: "string" } } },
          getValue: () => "Jane",
          renderValue: () => "Jane",
        },
        {
          column: { id: "age", columnDef: { meta: { dataType: "number" } } },
          getValue: () => 25,
          renderValue: () => "25",
        },
      ],
    },
    {
      getAllCells: () => [
        {
          column: { id: "name", columnDef: { meta: { dataType: "string" } } },
          getValue: () => "Alice",
          renderValue: () => "Alice",
        },
        {
          column: { id: "age", columnDef: { meta: { dataType: "number" } } },
          getValue: () => 35,
          renderValue: () => "35",
        },
      ],
    },
  ] as Array<Row<unknown>>;

  const mockClosePanel = vi.fn();

  it("navigates between rows using navigation buttons", () => {
    renderWithProviders(
      <DataSelectionPanel rows={mockRows} closePanel={mockClosePanel} />,
    );

    // Check initial state
    expect(screen.getByText("Row 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("John")).toBeInTheDocument();

    // Navigate to next row
    const nextButton = screen.getByRole("button", { name: "Next row" });
    fireEvent.click(nextButton);

    expect(screen.getByText("Row 2 of 3")).toBeInTheDocument();
    expect(screen.getByText("Jane")).toBeInTheDocument();

    // Navigate to previous row
    const prevButton = screen.getByRole("button", { name: "Previous row" });
    fireEvent.click(prevButton);

    expect(screen.getByText("Row 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("John")).toBeInTheDocument();

    // Navigate to last row
    const lastButton = screen.getByRole("button", { name: "Go to last row" });
    fireEvent.click(lastButton);

    expect(screen.getByText("Row 3 of 3")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();

    // Navigate to first row
    const firstButton = screen.getByRole("button", { name: "Go to first row" });
    fireEvent.click(firstButton);

    expect(screen.getByText("Row 1 of 3")).toBeInTheDocument();
    expect(screen.getByText("John")).toBeInTheDocument();
  });

  it("filters rows based on search input", () => {
    renderWithProviders(
      <DataSelectionPanel rows={mockRows} closePanel={mockClosePanel} />,
    );

    // Search for John
    const searchInput = screen.getByTestId("selection-panel-search-input");
    fireEvent.change(searchInput, { target: { value: "John" } });

    expect(screen.getByText("John")).toBeInTheDocument();
    // Check that the other column is not in the document
    expect(screen.queryByText(JOHNS_AGE.toString())).not.toBeInTheDocument();
  });

  it("renders copy button on hover", () => {
    renderWithProviders(
      <DataSelectionPanel rows={mockRows} closePanel={mockClosePanel} />,
    );

    const row = screen.getByText("John").closest("tr");
    if (row) {
      fireEvent.mouseEnter(row);
      expect(
        within(row).getByRole("button", { name: /copy to clipboard/i }),
      ).toBeInTheDocument();
    }
  });
});
