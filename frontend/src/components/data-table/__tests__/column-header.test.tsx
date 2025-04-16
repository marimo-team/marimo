/* Copyright 2024 Marimo. All rights reserved. */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PopoverSetFilter } from "../column-header";
import type { Column } from "@tanstack/react-table";

describe("PopoverSetFilter", () => {
  // Mock data and setup
  const mockSetIsSetFilterOpen = vi.fn();
  const mockCalculateTopKRows = vi.fn();
  const mockColumn = {
    id: "testColumn",
    setFilterValue: vi.fn(),
  } as unknown as Column<unknown>;

  const mockTopKData = [
    ["value1", 10],
    ["value2", 5],
    ["value3", 3],
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockCalculateTopKRows.mockResolvedValue({ data: mockTopKData });
  });

  it("should filter data based on search input", async () => {
    render(
      <PopoverSetFilter
        setIsSetFilterOpen={mockSetIsSetFilterOpen}
        calculateTopKRows={mockCalculateTopKRows}
        column={mockColumn}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("value1")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText("Search");
    fireEvent.change(searchInput, { target: { value: "value1" } });

    expect(screen.getByText("value1")).toBeInTheDocument();
    expect(screen.queryByText("value2")).not.toBeInTheDocument();
  });

  it("should handle checkbox selection correctly", async () => {
    render(
      <PopoverSetFilter
        setIsSetFilterOpen={mockSetIsSetFilterOpen}
        calculateTopKRows={mockCalculateTopKRows}
        column={mockColumn}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("value1")).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]); // First row checkbox (after "Select all")

    const applyButton = screen.getByText("Apply");
    fireEvent.click(applyButton);

    expect(mockColumn.setFilterValue).toHaveBeenCalledWith({
      options: ["value1"],
      type: "select",
    });
  });

  it('should handle "Select all" checkbox correctly', async () => {
    render(
      <PopoverSetFilter
        setIsSetFilterOpen={mockSetIsSetFilterOpen}
        calculateTopKRows={mockCalculateTopKRows}
        column={mockColumn}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("value1")).toBeInTheDocument();
    });

    const selectAllCheckbox = screen.getByLabelText("Select all");
    fireEvent.click(selectAllCheckbox);

    const applyButton = screen.getByText("Apply");
    fireEvent.click(applyButton);

    expect(mockColumn.setFilterValue).toHaveBeenCalledWith({
      type: "select",
      options: ["value1", "value2", "value3"],
    });
  });

  it("should handle error state correctly", async () => {
    mockCalculateTopKRows.mockRejectedValue(new Error("Test error"));

    render(
      <PopoverSetFilter
        setIsSetFilterOpen={mockSetIsSetFilterOpen}
        calculateTopKRows={mockCalculateTopKRows}
        column={mockColumn}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  it("should clear filters when clear button is clicked", async () => {
    render(
      <PopoverSetFilter
        setIsSetFilterOpen={mockSetIsSetFilterOpen}
        calculateTopKRows={mockCalculateTopKRows}
        column={mockColumn}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("value1")).toBeInTheDocument();
    });

    // Select some values
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    // Click clear button
    const clearButton = screen.getByText("Clear");
    fireEvent.click(clearButton);

    // Verify all checkboxes are unchecked
    checkboxes.forEach((checkbox) => {
      expect(checkbox).not.toBeChecked();
    });
  });
});
