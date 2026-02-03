/* Copyright 2026 Marimo. All rights reserved. */

import { TooltipProvider } from "@radix-ui/react-tooltip";
import { act, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { DownloadAsArgs } from "@/components/data-table/schemas";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import { store } from "@/core/state/jotai";
import {
  type GetDataUrl,
  type GetRowIds,
  LoadingDataTableComponent,
} from "../DataTablePlugin";

beforeAll(() => {
  global.ResizeObserver = class ResizeObserver {
    observe() {
      // do nothing
    }
    unobserve() {
      // do nothing
    }
    disconnect() {
      // do nothing
    }
  };
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
      enableSearch: true,
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
