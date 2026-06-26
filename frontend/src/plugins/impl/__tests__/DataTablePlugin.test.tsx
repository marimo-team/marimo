/* Copyright 2026 Marimo. All rights reserved. */

import { Tooltip } from "radix-ui";

const TooltipProvider = Tooltip.Provider;

import { act, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import type { DownloadAsArgs } from "@/components/data-table/schemas";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import { store } from "@/core/state/jotai";
import {
  type GetDataUrl,
  type GetRowIds,
  LoadingDataTableComponent,
} from "../DataTablePlugin";

// Default to normal (non-static) mode; individual tests flip this on.
const mockIsStatic = vi.fn().mockReturnValue(false);
vi.mock("@/core/static/static-state", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/core/static/static-state")>();
  return { ...actual, isStaticNotebook: () => mockIsStatic() };
});

beforeAll(() => {
  SetupMocks.resizeObserver();
});

describe("LoadingDataTableComponent", () => {
  /**
   * Regression test for https://github.com/marimo-team/marimo/issues/8023
   *
   * When a table is replaced via mo.output.replace() with updated data,
   * but the initial page data (unsorted first page) hasn't changed,
   * the useAsyncData hook's deps may all remain the same.
   * Previously, the `search` function reference was memoized on
   * [plugin.functions, hostElement] and wouldn't change on reset(),
   * so the useAsyncData effect wouldn't re-fire.
   *
   * The fix adds a resetNonce to the functionMethods memo deps,
   * so when the plugin is reset (table instance changes), the search
   * function reference changes, triggering useAsyncData to re-fetch.
   *
   * This test verifies that when the search function reference changes
   * (simulating reset()), the component re-fetches data even if
   * props.data hasn't changed.
   */
  it("should refetch data when search function reference changes", async () => {
    const host = document.createElement("div");
    const setValue = vi.fn();

    // The initial page data string - identical for both renders.
    // This simulates the case where only a row on page 2 changed,
    // so the first page data is the same.
    const initialPageData = JSON.stringify([
      { id: 1, status: "pending", value: 10 },
      { id: 2, status: "pending", value: 20 },
      { id: 3, status: "pending", value: 30 },
    ]);

    const searchResult = {
      data: [
        { id: 1, status: "pending", value: 10 },
        { id: 2, status: "pending", value: 20 },
        { id: 3, status: "pending", value: 30 },
      ],
      total_rows: 4,
      cell_styles: null,
      cell_hover_texts: null,
    };

    const searchFn1 = vi.fn().mockResolvedValue(searchResult);
    const searchFn2 = vi.fn().mockResolvedValue(searchResult);

    const fieldTypes: FieldTypesWithExternalType = [
      ["id", ["integer", "integer"]],
      ["status", ["string", "string"]],
      ["value", ["integer", "integer"]],
    ];

    const commonProps = {
      label: null,
      totalRows: 4,
      pagination: true,
      pageSize: 3,
      selection: "single" as const,
      showDownload: false,
      showFilters: false,
      showColumnSummaries: false as const,
      showDataTypes: false,
      showPageSizeSelector: false,
      showColumnExplorer: false,
      showRowExplorer: false,
      showChartBuilder: false,
      rowHeaders: [] as FieldTypesWithExternalType,
      fieldTypes,
      totalColumns: 3,
      maxColumns: "all" as const,
      hasStableRowId: false,
      lazy: false,
      host,
      showSearch: true,
      value: [] as (number | string | { rowId: string; columnName?: string })[],
      setValue,
      download_as: vi.fn() as DownloadAsArgs,
      get_column_summaries: vi.fn().mockResolvedValue({
        data: null,
        stats: {},
        bin_values: {},
        value_counts: {},
        show_charts: false,
      }),
      get_data_url: vi.fn() as GetDataUrl,
      get_row_ids: vi.fn() as GetRowIds,
      get_size_bytes: vi.fn().mockResolvedValue({ size_bytes: null }),
    };

    const Wrapper = ({ children }: { children: React.ReactNode }) => (
      <Provider store={store}>
        <TooltipProvider>{children}</TooltipProvider>
      </Provider>
    );

    // Render with first search function
    const { rerender } = render(
      <Wrapper>
        <LoadingDataTableComponent
          {...commonProps}
          data={initialPageData}
          search={searchFn1}
        />
      </Wrapper>,
    );

    // Wait for the table to render with data
    await waitFor(() => {
      expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
    });

    // Search was called on initial load (fire-and-forget for canShowInitialPage)
    expect(searchFn1).toHaveBeenCalled();

    // Now rerender with the same data but a NEW search function reference.
    // This simulates what happens after reset() when resetNonce increments
    // and functionMethods is recreated.
    await act(async () => {
      rerender(
        <Wrapper>
          <LoadingDataTableComponent
            {...commonProps}
            data={initialPageData}
            search={searchFn2}
          />
        </Wrapper>,
      );
    });

    // The new search function should be called because the search
    // dependency changed in useAsyncData.
    await waitFor(() => {
      expect(searchFn2).toHaveBeenCalled();
    });
  });
});

describe("static notebook control suppression", () => {
  const fieldTypes: FieldTypesWithExternalType = [
    ["id", ["integer", "integer"]],
    ["name", ["string", "string"]],
  ];

  // Only the first page is embedded in a static export; the total is larger.
  const TOTAL_ROWS = 50;
  const PAGE_SIZE = 10;
  const firstPage = JSON.stringify(
    Array.from({ length: PAGE_SIZE }, (_, i) => ({
      id: i + 1,
      name: `item-${i + 1}`,
    })),
  );

  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <TooltipProvider>{children}</TooltipProvider>
    </Provider>
  );

  const makeProps = () => {
    const host = document.createElement("div");
    return {
      label: null,
      totalRows: TOTAL_ROWS,
      pagination: true,
      pageSize: PAGE_SIZE,
      selection: "multi" as const,
      showDownload: true,
      showFilters: true,
      showColumnSummaries: true as const,
      showDataTypes: true,
      showPageSizeSelector: true,
      showColumnExplorer: false,
      showRowExplorer: false,
      showChartBuilder: false,
      rowHeaders: [] as FieldTypesWithExternalType,
      fieldTypes,
      totalColumns: 2,
      maxColumns: "all" as const,
      hasStableRowId: true,
      lazy: false,
      host,
      showSearch: true,
      value: [] as (number | string | { rowId: string; columnName?: string })[],
      setValue: vi.fn(),
      data: firstPage,
      search: vi.fn().mockResolvedValue({
        data: firstPage,
        total_rows: TOTAL_ROWS,
        cell_styles: null,
        cell_hover_texts: null,
      }),
      download_as: vi.fn() as DownloadAsArgs,
      get_column_summaries: vi.fn().mockResolvedValue({
        data: null,
        stats: {},
        bin_values: {},
        value_counts: {},
        show_charts: false,
      }),
      get_data_url: vi.fn() as GetDataUrl,
      get_row_ids: vi.fn() as GetRowIds,
      get_size_bytes: vi.fn().mockResolvedValue({ size_bytes: null }),
    };
  };

  beforeEach(() => {
    mockIsStatic.mockReturnValue(false);
  });

  it("renders kernel-dependent controls in normal mode", async () => {
    const props = makeProps();
    render(
      <Wrapper>
        <LoadingDataTableComponent {...props} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
    });

    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
    expect(screen.getByTestId("next-page-button")).toBeInTheDocument();
    expect(screen.getByTestId("select-all-checkbox")).toBeInTheDocument();
    expect(props.get_column_summaries).toHaveBeenCalled();
    expect(screen.queryByText(/Showing the first/)).not.toBeInTheDocument();
  });

  it("suppresses kernel-dependent controls in static mode", async () => {
    mockIsStatic.mockReturnValue(true);
    const props = makeProps();
    render(
      <Wrapper>
        <LoadingDataTableComponent {...props} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
    });

    // Top bar (search), pagination, and the selection column are gone.
    expect(screen.queryByPlaceholderText("Search...")).not.toBeInTheDocument();
    expect(screen.queryByTestId("next-page-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("select-all-checkbox")).not.toBeInTheDocument();
    // Column summaries never hit the kernel.
    expect(props.get_column_summaries).not.toHaveBeenCalled();
    // The truncation banner explains the missing rows.
    expect(screen.getByText(/Showing the first/)).toBeInTheDocument();
  });

  it("suppresses search even when the author opts in via showSearch", async () => {
    mockIsStatic.mockReturnValue(true);
    const props = makeProps();
    render(
      <Wrapper>
        <LoadingDataTableComponent {...props} showSearch={true} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getAllByRole("row").length).toBeGreaterThan(1);
    });

    expect(screen.queryByPlaceholderText("Search...")).not.toBeInTheDocument();
  });
});
