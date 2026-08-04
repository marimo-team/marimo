/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import { getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { TableTopBar } from "../TableTopBar";

const TestTableTopBar = ({
  onAiSearch,
}: {
  onAiSearch: (query: string) => void;
}) => {
  const table = useReactTable({
    data: [],
    columns: [],
    getCoreRowModel: getCoreRowModel(),
    locale: "en-US",
  });

  return (
    <TooltipProvider>
      <TableTopBar
        table={table}
        showSearch={true}
        onSearchQueryChange={vi.fn()}
        onAiSearch={onAiSearch}
      />
    </TooltipProvider>
  );
};

describe("TableTopBar", () => {
  it.each([
    ["Command", { metaKey: true }],
    ["Control", { ctrlKey: true }],
  ])("runs AI search with %s+Enter", (_modifier, eventInit) => {
    const onAiSearch = vi.fn();
    render(<TestTableTopBar onAiSearch={onAiSearch} />);

    const input = screen.getByPlaceholderText("Search...");
    fireEvent.change(input, { target: { value: "high revenue" } });
    fireEvent.keyDown(input, { key: "Enter", ...eventInit });

    expect(onAiSearch).toHaveBeenCalledWith("high revenue");
  });

  it("gives the AI search button an accessible name", () => {
    render(<TestTableTopBar onAiSearch={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: "Search with AI" }),
    ).toBeInTheDocument();
  });
});
