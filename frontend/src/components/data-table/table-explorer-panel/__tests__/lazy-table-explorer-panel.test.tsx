/* Copyright 2026 Marimo. All rights reserved. */

import { getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LazyTableExplorerPanel } from "../lazy-table-explorer-panel";

vi.mock("../table-explorer-panel", () => ({
  TableExplorerPanel: ({ rowIdx }: { rowIdx: number }) => (
    <div>Explorer row {rowIdx}</div>
  ),
}));

vi.mock("@/utils/lazy", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/lazy")>();
  return {
    reactLazyWithPreload: (
      factory: Parameters<typeof actual.reactLazyWithPreload>[0],
    ) =>
      actual.reactLazyWithPreload(
        vi
          .fn(factory)
          .mockRejectedValueOnce(new Error("Chunk download failed")),
      ),
  };
});

function TestExplorer() {
  const table = useReactTable<unknown>({
    data: [],
    columns: [],
    locale: "en-US",
    getCoreRowModel: getCoreRowModel(),
  });
  return (
    <LazyTableExplorerPanel
      table={table}
      tableId="table"
      rowIdx={3}
      setRowIdx={vi.fn()}
      totalRows={4}
      totalColumns={1}
      fieldTypes={[]}
      getRow={vi.fn()}
      isSelectable={false}
      isRowSelected={false}
      showRowExplorer={true}
      showColumnExplorer={true}
      activeTab="row-viewer"
      onTabChange={vi.fn()}
    />
  );
}

it("retries a failed explorer download and preserves the selected row", async () => {
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => {
    // The boundary catches the expected chunk download error.
  });
  try {
    render(<TestExplorer />);
    expect(
      await screen.findByText("Could not load the explorer."),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Explorer row 3")).toBeVisible();
    expect(screen.queryByText("Could not load the explorer.")).toBeNull();
  } finally {
    consoleError.mockRestore();
  }
});
