/* Copyright 2026 Marimo. All rights reserved. */

import { Tooltip } from "radix-ui";

const TooltipProvider = Tooltip.Provider;

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { Provider } from "jotai";
import { useState } from "react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import type { DownloadAsFunction } from "@/components/data-table/schemas";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import { store } from "@/core/state/jotai";
import { Deferred } from "@/utils/Deferred";
import {
  type GetDataUrl,
  type GetRowIds,
  LoadingDataTableComponent,
} from "../DataTablePlugin";

// Default to normal (non-static) mode; individual tests flip this on.
const mockIsStatic = vi.fn().mockReturnValue(false);
vi.mock("@/utils/download", () => ({
  downloadByURL: vi.fn(),
  withLoadingToast: vi.fn(async (_title, callback) => callback()),
}));
vi.mock("@/core/static/static-state", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/core/static/static-state")>();
  return { ...actual, isStaticNotebook: () => mockIsStatic() };
});

beforeAll(() => {
  SetupMocks.resizeObserver();
});

describe("LoadingDataTableComponent", () => {
  it("keeps data columns and routes each export to its RPC", async () => {
    const host = document.createElement("div");
    const data = JSON.stringify([{ index: "first", value: 1 }]);
    const downloadAs = vi
      .fn()
      .mockResolvedValue({ url: "export", filename: "table.csv" });
    const downloadGeoJSON = vi
      .fn()
      .mockResolvedValue({ url: "export", filename: "table.geojson" });

    render(
      <Provider store={store}>
        <TooltipProvider>
          <LoadingDataTableComponent
            label={null}
            totalRows={1}
            pagination={false}
            pageSize={10}
            selection={null}
            showDownload={true}
            showFilters={false}
            showColumnSummaries={false}
            showDataTypes={false}
            showPageSizeSelector={false}
            showColumnExplorer={false}
            showRowExplorer={false}
            showChartBuilder={false}
            rowHeaders={[["index", ["string", "object"]]]}
            fieldTypes={undefined}
            totalColumns={1}
            maxColumns={1}
            hasStableRowId={false}
            lazy={false}
            host={host}
            showSearch={false}
            value={[]}
            setValue={vi.fn()}
            data={data}
            search={vi.fn().mockResolvedValue({
              data,
              total_rows: 1,
              cell_styles: null,
              cell_hover_texts: null,
            })}
            download_as={downloadAs}
            download_geojson={downloadGeoJSON}
            get_export_metadata={vi.fn().mockResolvedValue({
              geometry_columns: [
                { name: "value", encoding: "objects", crs: "EPSG:4326" },
              ],
              primary_geometry_column: "value",
              default_geometry_column: "value",
              formats: {
                geojson: {
                  available: true,
                  reason: null,
                  missing_packages: [],
                },
              },
            })}
            get_column_summaries={vi.fn()}
            get_data_url={vi.fn() as GetDataUrl}
            get_row_ids={vi.fn() as GetRowIds}
            get_size_bytes={vi.fn().mockResolvedValue({ size_bytes: null })}
          />
        </TooltipProvider>
      </Provider>,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("columnheader", { name: "value" }),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("export-button"));
    await screen.findByRole("dialog", { name: "Export table" });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Download GeoJSON" }),
      ).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Download GeoJSON" }));
    await waitFor(() =>
      expect(downloadGeoJSON).toHaveBeenCalledWith({
        format: "geojson",
        geometry_column: "value",
      }),
    );
    expect(downloadAs).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() =>
      expect(downloadAs).toHaveBeenCalledWith({ format: "csv" }),
    );
    expect(downloadGeoJSON).toHaveBeenCalledTimes(1);
  });

  it("refreshes export metadata when a dataframe transform changes the data", async () => {
    const host = document.createElement("div");
    const metadataFor = (name: string) => ({
      geometry_columns: [{ name, encoding: "objects", crs: "EPSG:4326" }],
      primary_geometry_column: name,
      default_geometry_column: name,
      formats: {
        parquet: { available: true, reason: null, missing_packages: [] },
      },
    });
    const getExportMetadata = vi
      .fn()
      .mockResolvedValueOnce(metadataFor("before"))
      .mockResolvedValueOnce(metadataFor("after"));
    const view = (data: string) => (
      <Provider store={store}>
        <TooltipProvider>
          <LoadingDataTableComponent
            label={null}
            totalRows={1}
            pagination={false}
            pageSize={10}
            selection={null}
            showDownload={true}
            showFilters={false}
            showColumnSummaries={false}
            showDataTypes={false}
            showPageSizeSelector={false}
            showColumnExplorer={false}
            showRowExplorer={false}
            showChartBuilder={false}
            rowHeaders={[]}
            fieldTypes={undefined}
            totalColumns={1}
            maxColumns="all"
            hasStableRowId={false}
            lazy={false}
            host={host}
            showSearch={false}
            value={[]}
            setValue={vi.fn()}
            data={data}
            search={vi.fn().mockResolvedValue({
              data,
              total_rows: 1,
              cell_styles: null,
              cell_hover_texts: null,
            })}
            download_as={vi.fn()}
            download_geojson={vi.fn()}
            get_export_metadata={getExportMetadata}
            get_column_summaries={vi.fn()}
            get_data_url={vi.fn() as GetDataUrl}
            get_row_ids={vi.fn() as GetRowIds}
            get_size_bytes={vi.fn().mockResolvedValue({ size_bytes: null })}
          />
        </TooltipProvider>
      </Provider>
    );
    const { rerender } = render(
      view(JSON.stringify([{ before: "POINT (1 2)" }])),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("columnheader", { name: "before" }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByTestId("export-button"));
    await waitFor(() =>
      expect(screen.getByTestId("export-summary-parquet")).toHaveTextContent(
        "before",
      ),
    );

    rerender(view(JSON.stringify([{ after: "POINT (3 4)" }])));

    await waitFor(() =>
      expect(screen.getByTestId("export-summary-parquet")).toHaveTextContent(
        "after",
      ),
    );
    expect(getExportMetadata).toHaveBeenCalledTimes(2);
  });

  it("does not log duplicate keys when a pivot becomes empty", async () => {
    const host = document.createElement("div");
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const populatedData = JSON.stringify([
      { DSGROUP: "a", no: 1, yes: 1 },
      { DSGROUP: "b", no: 0, yes: 1 },
    ]);
    const Wrapper = ({ children }: { children: React.ReactNode }) => (
      <Provider store={store}>
        <TooltipProvider>{children}</TooltipProvider>
      </Provider>
    );
    const commonProps = {
      label: null,
      pagination: false,
      pageSize: 10,
      selection: null,
      showDownload: false,
      showFilters: false,
      showColumnSummaries: false as const,
      showDataTypes: true,
      showPageSizeSelector: false,
      showColumnExplorer: false,
      showRowExplorer: false,
      showChartBuilder: false,
      rowHeaders: [
        ["DSGROUP", ["string", "object"]],
      ] as FieldTypesWithExternalType,
      maxColumns: "all" as const,
      hasStableRowId: false,
      lazy: false,
      host,
      showSearch: false,
      value: [] as (number | string | { rowId: string; columnName?: string })[],
      setValue: vi.fn(),
      download_as: vi.fn() as DownloadAsFunction,
      download_geojson: vi.fn(),
      get_export_metadata: vi.fn(),
      get_column_summaries: vi.fn(),
      get_data_url: vi.fn() as GetDataUrl,
      get_row_ids: vi.fn() as GetRowIds,
      get_size_bytes: vi.fn().mockResolvedValue({ size_bytes: null }),
    };

    try {
      const { rerender } = render(
        <Wrapper>
          <LoadingDataTableComponent
            {...commonProps}
            totalRows={2}
            totalColumns={2}
            fieldTypes={[
              ["no", ["number", "int64"]],
              ["yes", ["number", "int64"]],
            ]}
            data={populatedData}
            search={vi.fn().mockResolvedValue({
              data: populatedData,
              total_rows: 2,
              cell_styles: null,
              cell_hover_texts: null,
            })}
          />
        </Wrapper>,
      );

      await waitFor(() => {
        expect(screen.getAllByRole("row")).toHaveLength(3);
      });

      await act(async () => {
        rerender(
          <Wrapper>
            <LoadingDataTableComponent
              {...commonProps}
              totalRows={0}
              totalColumns={0}
              fieldTypes={undefined}
              data="[]"
              search={vi.fn().mockResolvedValue({
                data: "[]",
                total_rows: 0,
                cell_styles: null,
                cell_hover_texts: null,
              })}
            />
          </Wrapper>,
        );
      });

      await waitFor(() => {
        expect(screen.getByText("No results.")).toBeInTheDocument();
      });

      const duplicateKeyErrors = consoleError.mock.calls.filter((args) =>
        args.some((arg) => typeof arg === "string" && arg.includes("same key")),
      );
      expect(duplicateKeyErrors).toHaveLength(0);
    } finally {
      consoleError.mockRestore();
    }
  });

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
      download_as: vi.fn() as DownloadAsFunction,
      download_geojson: vi.fn(),
      get_export_metadata: vi.fn(),
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

describe("table pagination and static notebook control suppression", () => {
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
      download_as: vi.fn() as DownloadAsFunction,
      download_geojson: vi.fn(),
      get_export_metadata: vi.fn(),
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

  it("preserves the preview banner for ordinary paginated tables with unknown totals", async () => {
    const props = makeProps();
    render(
      <Wrapper>
        <LoadingDataTableComponent {...props} totalRows="too_many" />
      </Wrapper>,
    );
    expect(
      await screen.findByText("Previewing the first 10 rows."),
    ).toBeInTheDocument();
  });

  it("pages lazy results with unknown totals and resets search, sorting, and filters to page one", async () => {
    const props = makeProps();
    const search = vi
      .fn()
      .mockImplementation(
        async (request: {
          page_number: number;
          query?: string;
          sort?: { by: string; descending: boolean }[];
        }) => ({
          data: [
            { id: request.page_number + 1, name: request.query || "item" },
          ],
          total_rows: "too_many",
          has_next_page: request.page_number === 0,
        }),
      );
    render(
      <Wrapper>
        <LoadingDataTableComponent
          {...props}
          lazy={true}
          totalRows="too_many"
          selection={null}
          showColumnSummaries={false}
          search={search}
        />
      </Wrapper>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    expect(screen.getByText("Unknown, 2 columns")).toBeInTheDocument();
    expect(screen.queryByTestId("last-page-button")).not.toBeInTheDocument();
    expect(screen.queryByText(/Previewing the first/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 1 }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId("previous-page-button"));
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeDisabled(),
    );
    search.mockClear();
    fireEvent.change(screen.getByPlaceholderText("Search..."), {
      target: { value: "new" },
    });
    await waitFor(() =>
      expect(search).toHaveBeenCalledWith(
        expect.objectContaining({ query: "new", page_number: 0 }),
      ),
    );
    expect(
      search.mock.calls.every(([request]) => request.page_number === 0),
    ).toBe(true);
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeDisabled(),
    );
    search.mockClear();
    fireEvent.click(
      within(screen.getByRole("columnheader", { name: /name/ })).getByRole(
        "button",
        { name: "Sort column ascending" },
      ),
    );
    await waitFor(() =>
      expect(search).toHaveBeenCalledWith(
        expect.objectContaining({
          page_number: 0,
          sort: [{ by: "name", descending: false }],
        }),
      ),
    );
    expect(
      search.mock.calls.every(([request]) => request.page_number === 0),
    ).toBe(true);
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 1 }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeDisabled(),
    );
    search.mockClear();
    const columnMenu = within(
      screen.getByRole("columnheader", { name: /name/ }),
    ).getByRole("button", { name: "Column options" });
    fireEvent.keyDown(columnMenu, { key: "Enter" });
    fireEvent.click(await screen.findByRole("menuitem", { name: "Filter" }));
    fireEvent.change(screen.getByPlaceholderText("Text…"), {
      target: { value: "item" },
    });
    fireEvent.click(screen.getByLabelText("Apply filter"));
    await waitFor(() =>
      expect(search).toHaveBeenCalledWith(
        expect.objectContaining({
          page_number: 0,
          filters: expect.objectContaining({ children: expect.any(Array) }),
        }),
      ),
    );
    expect(
      search.mock.calls.every(([request]) => request.page_number === 0),
    ).toBe(true);
  });

  it.each(["success", "error"] as const)(
    "ignores a stale lazy page %s after the query changes",
    async (outcome) => {
      const props = makeProps();
      const initial = {
        data: [{ id: 1, name: "initial-page" }],
        total_rows: "too_many" as const,
        has_next_page: true,
      };
      const oldPage = new Deferred<typeof initial>();
      const newQuery = new Deferred<typeof initial>();
      const search = vi
        .fn()
        .mockResolvedValueOnce(initial)
        .mockReturnValueOnce(oldPage.promise)
        .mockReturnValueOnce(newQuery.promise);
      render(
        <Wrapper>
          <LoadingDataTableComponent
            {...props}
            lazy={true}
            totalRows="too_many"
            selection={null}
            showColumnSummaries={false}
            search={search}
          />
        </Wrapper>,
      );
      await screen.findByText("initial-page");
      fireEvent.click(screen.getByTestId("next-page-button"));
      await waitFor(() =>
        expect(search).toHaveBeenLastCalledWith(
          expect.objectContaining({ page_number: 1 }),
        ),
      );
      expect(screen.getByTestId("next-page-button")).toBeDisabled();

      fireEvent.change(screen.getByPlaceholderText("Search..."), {
        target: { value: "current" },
      });
      await waitFor(() =>
        expect(search).toHaveBeenLastCalledWith(
          expect.objectContaining({ query: "current", page_number: 0 }),
        ),
      );
      await act(async () => {
        newQuery.resolve({
          data: [{ id: 2, name: "latest-page" }],
          total_rows: "too_many",
          has_next_page: false,
        });
      });
      await screen.findByText("latest-page");

      await act(async () => {
        if (outcome === "success") {
          oldPage.resolve({
            ...initial,
            data: [{ id: 3, name: "stale-result" }],
          });
        } else {
          oldPage.reject(new Error("stale-page-error"));
        }
      });
      expect(screen.getByText("latest-page")).toBeInTheDocument();
      expect(screen.queryByText("stale-result")).not.toBeInTheDocument();
      expect(screen.queryByText("stale-page-error")).not.toBeInTheDocument();
      expect(screen.getByTestId("previous-page-button")).toBeDisabled();
      expect(screen.getByTestId("next-page-button")).toBeDisabled();
    },
  );

  it("recovers from a failed lazy page by navigating back", async () => {
    const props = makeProps();
    const initial = {
      data: [{ id: 1, name: "initial-page" }],
      total_rows: "too_many" as const,
      has_next_page: true,
    };
    const failedPage = new Deferred<typeof initial>();
    const search = vi
      .fn()
      .mockResolvedValueOnce(initial)
      .mockReturnValueOnce(failedPage.promise)
      .mockResolvedValueOnce({
        ...initial,
        data: [{ id: 1, name: "recovered-page" }],
      })
      .mockResolvedValueOnce({
        ...initial,
        data: [{ id: 2, name: "last-page" }],
        has_next_page: false,
      });
    render(
      <Wrapper>
        <LoadingDataTableComponent
          {...props}
          lazy={true}
          totalRows="too_many"
          selection={null}
          showColumnSummaries={false}
          search={search}
        />
      </Wrapper>,
    );
    await screen.findByText("initial-page");
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 1 }),
      ),
    );
    expect(screen.getByTestId("next-page-button")).toBeDisabled();
    expect(screen.getByText("initial-page")).toBeInTheDocument();
    await act(async () => {
      failedPage.reject(new Error("page-fetch-failed"));
    });
    await screen.findByText("page-fetch-failed");
    expect(screen.getByTestId("next-page-button")).toBeDisabled();
    expect(screen.getByTestId("previous-page-button")).toBeEnabled();

    fireEvent.click(screen.getByTestId("previous-page-button"));
    await screen.findByText("recovered-page");
    expect(search).toHaveBeenLastCalledWith(
      expect.objectContaining({ page_number: 0 }),
    );
    expect(screen.queryByText("page-fetch-failed")).not.toBeInTheDocument();
    expect(screen.getByTestId("next-page-button")).toBeEnabled();
    fireEvent.click(screen.getByTestId("next-page-button"));
    await screen.findByText("last-page");
    expect(screen.getByTestId("next-page-button")).toBeDisabled();
  });

  it("requests only the first page with the new configured page size", async () => {
    const props = makeProps();
    const view = (pageSize: number) => (
      <Wrapper>
        <LoadingDataTableComponent {...props} pageSize={pageSize} />
      </Wrapper>
    );
    const { rerender } = render(view(PAGE_SIZE));
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(props.search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 1, page_size: PAGE_SIZE }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    props.search.mockClear();

    rerender(view(5));
    await waitFor(() => expect(props.search).toHaveBeenCalled());
    expect(
      props.search.mock.calls.every(
        ([request]) => request.page_number === 0 && request.page_size === 5,
      ),
    ).toBe(true);
  });

  it("preserves a new page size when a pending response changes the row count in the same batch", async () => {
    const props = makeProps();
    const Harness = () => {
      const [pageSize, setPageSize] = useState(PAGE_SIZE);
      return (
        <Wrapper>
          <button type="button" onClick={() => setPageSize(5)}>
            Change configured page size
          </button>
          <LoadingDataTableComponent {...props} pageSize={pageSize} />
        </Wrapper>
      );
    };
    render(<Harness />);
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    const response = {
      data: firstPage,
      total_rows: 25,
      cell_styles: null,
      cell_hover_texts: null,
    };
    const pendingPage = new Deferred<typeof response>();
    props.search.mockReturnValueOnce(pendingPage.promise);
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(props.search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 1, page_size: PAGE_SIZE }),
      ),
    );
    props.search.mockClear();

    await act(async () => {
      pendingPage.resolve(response);
      // Settle the table-loading promises without committing the queued render.
      await new Promise((resolve) => setTimeout(resolve, 0));
      fireEvent.click(
        screen.getByRole("button", { name: "Change configured page size" }),
      );
    });

    await waitFor(() => expect(props.search).toHaveBeenCalled());
    expect(props.search).toHaveBeenLastCalledWith(
      expect.objectContaining({ page_number: 0, page_size: 5 }),
    );
  });

  it("returns to the first page when a refreshed result changes the row count", async () => {
    const props = makeProps();
    const view = () => (
      <Wrapper>
        <LoadingDataTableComponent {...props} />
      </Wrapper>
    );
    const { rerender } = render(view());
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    fireEvent.click(screen.getByTestId("next-page-button"));
    await waitFor(() =>
      expect(props.search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 1 }),
      ),
    );
    await waitFor(() =>
      expect(screen.getByTestId("next-page-button")).toBeEnabled(),
    );
    props.search = vi.fn().mockResolvedValue({
      data: firstPage,
      total_rows: 25,
      cell_styles: null,
      cell_hover_texts: null,
    });

    rerender(view());
    await waitFor(() =>
      expect(props.search).toHaveBeenLastCalledWith(
        expect.objectContaining({ page_number: 0, page_size: PAGE_SIZE }),
      ),
    );
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
