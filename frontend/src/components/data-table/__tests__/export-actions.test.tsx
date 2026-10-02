/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { viewStateAtom, type AppMode } from "@/core/mode";
import { copyToClipboard } from "@/utils/copy";
import { downloadByURL } from "@/utils/download";
import { jsonToMarkdown } from "@/utils/json/json-parser";
import { downloadSizeLimitAtom } from "../download-policy/atoms";
import { ExportActions, type ExportActionProps } from "../export-actions";
import type { ExportMetadata } from "../schemas";

const mocks = vi.hoisted(() => ({
  handleInstallPackages: vi.fn(),
}));

vi.mock("@/core/packages/useInstallPackage", () => ({
  useInstallPackages: () => ({
    handleInstallPackages: mocks.handleInstallPackages,
  }),
}));

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/utils/download", () => ({
  downloadByURL: vi.fn(),
  withLoadingToast: vi.fn(
    async (_title: string, callback: () => Promise<unknown>) => callback(),
  ),
}));

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(() => ({
    dismiss: vi.fn(),
    update: vi.fn(),
  })),
}));

const downloadAs = vi.fn<ExportActionProps["downloadAs"]>();

function renderExportActions(
  props: Partial<ExportActionProps> = {},
  sizeLimit: { limitBytes: number; unavailableMessage: string } | null = null,
  mode: AppMode = "edit",
) {
  const store = createStore();
  store.set(downloadSizeLimitAtom, sizeLimit);
  store.set(viewStateAtom, { mode, cellAnchor: null });

  const view = (nextProps: Partial<ExportActionProps>) => (
    <Provider store={store}>
      <TooltipProvider delayDuration={0}>
        <ExportActions downloadAs={downloadAs} {...nextProps} />
      </TooltipProvider>
    </Provider>
  );
  const result = render(view(props));
  return {
    ...result,
    rerenderExportActions: (nextProps: Partial<ExportActionProps>) =>
      result.rerender(view(nextProps)),
  };
}

async function openDialog() {
  fireEvent.click(screen.getByTestId("export-button"));
  return screen.findByRole("dialog", { name: "Export table" });
}

function selectGeometry(name: string) {
  const select = screen.getByRole("combobox", { name: "Primary geometry" });
  const option = within(select).getByRole("option", {
    name,
  }) as HTMLOptionElement;
  fireEvent.change(select, { target: { value: option.value } });
}

const geometryMetadata: ExportMetadata = {
  geometry_columns: [
    { name: "location", encoding: "objects", crs: "EPSG:4326" },
    { name: "boundary", encoding: "objects", crs: null },
  ],
  primary_geometry_column: "location",
  default_geometry_column: "location",
  formats: {
    parquet: { available: true, reason: null, missing_packages: [] },
  },
};

describe("ExportActions dialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadAs.mockResolvedValue({
      url: "https://example.test/export",
      filename: "table",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("selects a primary geometry for GeoParquet without changing other formats", async () => {
    const getExportMetadata = vi.fn().mockResolvedValue(geometryMetadata);
    renderExportActions({ getExportMetadata });
    await openDialog();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "GeoParquet options" }),
      ).toBeEnabled();
    });
    expect(screen.getByTestId("export-summary-parquet")).toHaveTextContent(
      "location",
    );
    fireEvent.click(screen.getByRole("button", { name: "GeoParquet options" }));
    selectGeometry("boundary");
    fireEvent.click(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    );
    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalled();
    });
    expect(downloadAs).toHaveBeenCalledWith({
      format: "parquet",
      geometry_column: "boundary",
    });
    expect(getExportMetadata).toHaveBeenCalledWith({});
    expect(screen.getByText("GeoParquet")).toBeInTheDocument();
    expect(
      screen.getByText("Parquet with geometry and CRS metadata"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("export-summary-parquet")).toHaveTextContent(
      "boundary",
    );

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledWith({ format: "csv" });
    });
  });

  it("requires a choice when several geometries have no primary", async () => {
    renderExportActions({
      getExportMetadata: vi.fn().mockResolvedValue({
        ...geometryMetadata,
        primary_geometry_column: null,
        default_geometry_column: null,
      }),
    });
    await openDialog();
    await screen.findByRole("button", { name: "GeoParquet options" });
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeDisabled();
    expect(
      screen.getByText(
        "Choose a primary geometry column to export GeoParquet.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "GeoParquet options" }));
    selectGeometry("boundary");
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeEnabled();
  });

  it("shows ineligible geometry sources and keeps ordinary exports available", async () => {
    renderExportActions({
      getExportMetadata: vi.fn().mockResolvedValue({
        ...geometryMetadata,
        formats: {
          parquet: {
            available: false,
            reason: "GeoParquet export from Arrow tables is not supported yet.",
            missing_packages: [],
          },
        },
      }),
    });
    await openDialog();
    expect(
      await screen.findByText(
        "GeoParquet export from Arrow tables is not supported yet.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));
    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledWith({ format: "json" });
    });
  });

  it("keeps the geometry choice through a package install retry", async () => {
    const getExportMetadata = vi.fn().mockResolvedValue(geometryMetadata);
    downloadAs
      .mockResolvedValueOnce({
        url: "",
        filename: "",
        error: "GeoParquet export requires pyarrow.",
        code: "missing_packages",
        missing_packages: ["pyarrow"],
      })
      .mockResolvedValueOnce({
        url: "https://example.test/export",
        filename: "table",
      });
    renderExportActions({ getExportMetadata });
    await openDialog();
    await screen.findByRole("button", { name: "GeoParquet options" });
    fireEvent.click(screen.getByRole("button", { name: "GeoParquet options" }));
    selectGeometry("boundary");
    fireEvent.click(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    );
    expect(
      await screen.findByText("GeoParquet export requires pyarrow."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeDisabled();
    expect(downloadByURL).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Install pyarrow" }));
    expect(mocks.handleInstallPackages).toHaveBeenCalledWith(
      ["pyarrow"],
      expect.any(Function),
    );
    await act(async () => {
      mocks.handleInstallPackages.mock.calls[0][1]();
    });
    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalled();
    });
    expect(downloadAs).toHaveBeenLastCalledWith({
      format: "parquet",
      geometry_column: "boundary",
    });
  });

  it("refreshes eligibility after package installation", async () => {
    const getExportMetadata = vi.fn().mockResolvedValue({
      ...geometryMetadata,
      formats: {
        parquet: {
          available: false,
          reason: "GeoParquet export requires pyarrow.",
          missing_packages: ["pyarrow"],
        },
      },
    });
    renderExportActions({ getExportMetadata });
    await openDialog();
    await screen.findByRole("button", { name: "GeoParquet options" });
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeDisabled();
    expect(
      screen.getAllByText("GeoParquet export requires pyarrow."),
    ).toHaveLength(1);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(downloadAs).not.toHaveBeenCalled();
    fireEvent.click(
      await screen.findByRole("button", { name: "Install pyarrow" }),
    );
    getExportMetadata.mockResolvedValue(geometryMetadata);
    await act(async () => {
      mocks.handleInstallPackages.mock.calls[0][1]();
    });
    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalled();
    });
    expect(getExportMetadata).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByText("GeoParquet export requires pyarrow."),
    ).not.toBeInTheDocument();
  });

  it("keeps the install prompt when the package is still missing", async () => {
    const getExportMetadata = vi.fn().mockResolvedValue({
      ...geometryMetadata,
      formats: {
        parquet: {
          available: false,
          reason: "GeoParquet export requires pyarrow.",
          missing_packages: ["pyarrow"],
        },
      },
    });
    renderExportActions({ getExportMetadata });
    await openDialog();
    fireEvent.click(
      await screen.findByRole("button", { name: "Install pyarrow" }),
    );
    await act(async () => {
      mocks.handleInstallPackages.mock.calls[0][1]();
    });
    await waitFor(() => {
      expect(getExportMetadata).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.getByRole("button", { name: "Install pyarrow" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeDisabled();
    expect(downloadAs).not.toHaveBeenCalled();
  });

  it("can select a geometry column with an empty name", async () => {
    renderExportActions({
      getExportMetadata: vi.fn().mockResolvedValue({
        ...geometryMetadata,
        geometry_columns: [
          geometryMetadata.geometry_columns[0],
          { name: "", encoding: "objects", crs: null },
        ],
      }),
    });
    await openDialog();
    fireEvent.click(
      await screen.findByRole("button", { name: "GeoParquet options" }),
    );
    selectGeometry("(unnamed geometry)");
    fireEvent.click(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    );
    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledWith({
        format: "parquet",
        geometry_column: "",
      });
    });
  });

  it("refreshes geometry metadata when the source changes", async () => {
    const first = vi.fn().mockResolvedValue(geometryMetadata);
    const second = vi.fn().mockResolvedValue({
      ...geometryMetadata,
      geometry_columns: [
        { name: "region", encoding: "objects", crs: "EPSG:3857" },
      ],
      primary_geometry_column: "region",
      default_geometry_column: "region",
    });
    const { rerenderExportActions } = renderExportActions({
      getExportMetadata: first,
      metadataSource: "first",
    });
    await openDialog();
    await screen.findByRole("button", { name: "GeoParquet options" });
    fireEvent.click(screen.getByRole("button", { name: "GeoParquet options" }));
    selectGeometry("boundary");

    rerenderExportActions({
      getExportMetadata: second,
      metadataSource: "second",
    });
    await waitFor(() => {
      expect(screen.getByTestId("export-summary-parquet")).toHaveTextContent(
        "region",
      );
    });
    expect(
      screen.getByRole("combobox", { name: "Primary geometry" }),
    ).toHaveDisplayValue("region");
    fireEvent.click(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    );
    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledWith({
        format: "parquet",
        geometry_column: "region",
      });
    });
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("keeps a still-valid geometry override when metadata refreshes", async () => {
    const getExportMetadata = vi.fn().mockResolvedValue(geometryMetadata);
    const { rerenderExportActions } = renderExportActions({
      getExportMetadata,
      metadataSource: "first",
    });
    await openDialog();
    fireEvent.click(
      await screen.findByRole("button", { name: "GeoParquet options" }),
    );
    selectGeometry("boundary");
    rerenderExportActions({ getExportMetadata, metadataSource: "second" });
    await waitFor(() => {
      expect(getExportMetadata).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.getByRole("combobox", { name: "Primary geometry" }),
    ).toHaveDisplayValue("boundary");
  });

  it("does not publish an artifact for a structured failure without an error message", async () => {
    downloadAs.mockResolvedValueOnce({
      url: "",
      filename: "",
      code: "invalid_geometry",
      column: "location",
    });
    renderExportActions({
      getExportMetadata: vi.fn().mockResolvedValue(geometryMetadata),
    });
    await openDialog();
    await screen.findByRole("button", { name: "GeoParquet options" });
    fireEvent.click(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    );
    expect(
      await screen.findByText("The export did not produce a file."),
    ).toBeInTheDocument();
    expect(downloadByURL).not.toHaveBeenCalled();
  });

  it("retries a failed metadata lookup without blocking ordinary formats", async () => {
    const getExportMetadata = vi
      .fn()
      .mockRejectedValueOnce(new Error("Connection lost"))
      .mockResolvedValueOnce(geometryMetadata);
    renderExportActions({ getExportMetadata });
    await openDialog();
    expect(
      await screen.findByText(
        "Could not load geometry options: Connection lost",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download Parquet" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledWith({ format: "csv" });
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(
      await screen.findByRole("button", { name: "GeoParquet options" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download GeoParquet" }),
    ).toBeEnabled();
    expect(getExportMetadata).toHaveBeenCalledTimes(2);
  });

  it("does not cancel a pending CSV download when geometry metadata is retried", async () => {
    let resolveDownload: (value: { url: string; filename: string }) => void =
      () => undefined;
    downloadAs.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveDownload = resolve;
        }),
    );
    const getExportMetadata = vi
      .fn()
      .mockRejectedValueOnce(new Error("Connection lost"))
      .mockResolvedValueOnce(geometryMetadata);
    renderExportActions({ getExportMetadata });
    await openDialog();
    await screen.findByText("Could not load geometry options: Connection lost");

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByRole("button", { name: "GeoParquet options" });
    await act(async () => {
      resolveDownload({ url: "https://example.test/export", filename: "table" });
    });

    expect(downloadByURL).toHaveBeenCalledWith(
      expect.stringContaining("https://example.test/export"),
      "table.csv",
    );
  });

  it("cancels a pending download when the table source changes", async () => {
    let resolveDownload: (value: { url: string; filename: string }) => void =
      () => undefined;
    downloadAs.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveDownload = resolve;
        }),
    );
    const getExportMetadata = vi.fn().mockResolvedValue(geometryMetadata);
    const { rerenderExportActions } = renderExportActions({
      getExportMetadata,
      metadataSource: "first",
    });
    await openDialog();
    await screen.findByRole("button", { name: "GeoParquet options" });

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    rerenderExportActions({ getExportMetadata, metadataSource: "second" });
    await waitFor(() => {
      expect(getExportMetadata).toHaveBeenCalledTimes(2);
    });
    await act(async () => {
      resolveDownload({ url: "https://example.test/export", filename: "table" });
    });

    expect(downloadByURL).not.toHaveBeenCalled();
  });

  it("shows formats in the approved order with an options toggle where supported", async () => {
    renderExportActions();
    const dialog = await openDialog();
    const list = within(dialog).getByRole("list", { name: "Export formats" });
    const rows = within(list).getAllByRole("listitem");

    expect(rows.map((row) => row.dataset.testid)).toEqual([
      "export-row-csv",
      "export-row-tsv",
      "export-row-json",
      "export-row-parquet",
      "export-row-markdown",
    ]);
    for (const format of ["csv", "tsv", "json", "parquet", "markdown"]) {
      expect(
        screen.getByTestId(`export-format-icon-${format}`),
      ).toBeInTheDocument();
    }
    for (const label of ["CSV", "TSV", "JSON"]) {
      expect(
        screen.getByRole("button", { name: `${label} options` }),
      ).toHaveAttribute("aria-expanded", "false");
    }
    for (const label of ["Parquet", "Markdown"]) {
      expect(
        screen.queryByRole("button", { name: `${label} options` }),
      ).not.toBeInTheDocument();
    }
    expect(within(dialog).queryByRole("group")).not.toBeInTheDocument();
  });

  it("expands one options panel at a time", async () => {
    renderExportActions();
    const dialog = await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "CSV options" }));
    expect(
      within(dialog).getByRole("group", { name: "CSV options" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Delimiter" })).toHaveValue(
      ",",
    );
    expect(screen.getByRole("combobox", { name: "Encoding" })).toHaveValue(
      "utf-8",
    );

    fireEvent.click(screen.getByRole("button", { name: "JSON options" }));
    expect(
      within(dialog).queryByRole("group", { name: "CSV options" }),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByRole("group", { name: "JSON options" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: "Escape non-ASCII" }),
    ).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "JSON options" }));
    expect(within(dialog).queryByRole("group")).not.toBeInTheDocument();
  });

  it("sends only changed CSV options with a download", async () => {
    renderExportActions();
    await openDialog();
    expect(screen.getByTestId("export-summary-csv")).toHaveTextContent(
      "Comma · UTF-8",
    );
    expect(screen.queryByTestId("export-summary-parquet")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "CSV options" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Delimiter" }), {
      target: { value: ";" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Encoding" }), {
      target: { value: "utf-8-sig" },
    });
    expect(screen.getByTestId("export-summary-csv")).toHaveTextContent(
      "Semicolon · UTF-8 with BOM",
    );
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalled();
    });
    expect(downloadAs).toHaveBeenCalledWith({
      format: "csv",
      options: { separator: ";", encoding: "utf-8-sig" },
    });
  });

  it("keeps the delimiter but drops the encoding for a CSV copy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: vi.fn().mockResolvedValue("name;value\n"),
      }),
    );
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "CSV options" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Delimiter" }), {
      target: { value: ";" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "Encoding" }), {
      target: { value: "latin-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Copy CSV" }));

    await waitFor(() => {
      expect(copyToClipboard).toHaveBeenCalledWith("name;value\n");
    });
    expect(downloadAs).toHaveBeenCalledWith({
      format: "csv",
      options: { separator: ";" },
    });
  });

  it("sends the JSON escape setting only when turned off", async () => {
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "JSON options" }));
    fireEvent.click(screen.getByRole("switch", { name: "Escape non-ASCII" }));
    fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));

    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalled();
    });
    expect(downloadAs).toHaveBeenCalledWith({
      format: "json",
      options: { ensure_ascii: false },
    });
  });

  it("resets options and panels when the dialog closes", async () => {
    renderExportActions();
    let dialog = await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "CSV options" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Delimiter" }), {
      target: { value: "|" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    dialog = await openDialog();
    expect(within(dialog).queryByRole("group")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledWith({ format: "csv" });
    });
  });

  it("opens without showing an action tooltip", async () => {
    renderExportActions();
    const dialog = await openDialog();
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    expect(dialog).toHaveFocus();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("uses named icon buttons and reserves unavailable actions", async () => {
    renderExportActions();
    await openDialog();

    for (const format of ["CSV", "TSV", "JSON"]) {
      expect(
        screen.getByRole("button", { name: `Download ${format}` }),
      ).toBeEnabled();
      expect(
        screen.getByRole("button", { name: `Copy ${format}` }),
      ).toBeEnabled();
    }

    expect(
      screen.getByRole("button", { name: "Download Parquet" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "Copy Parquet" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Download Markdown" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Copy Markdown" })).toBeEnabled();
  });

  it.each([
    ["CSV", "csv"],
    ["TSV", "tsv"],
    ["JSON", "json"],
    ["Parquet", "parquet"],
  ] as const)(
    "downloads %s with its existing URL contract",
    async (label, format) => {
      downloadAs.mockResolvedValue({
        url: "https://example.test/export?token=abc",
        filename: "table.source",
      });
      renderExportActions();
      await openDialog();

      fireEvent.click(
        screen.getByRole("button", { name: `Download ${label}` }),
      );

      await waitFor(() => {
        expect(downloadByURL).toHaveBeenCalledWith(
          `https://example.test/export?token=abc&download=1&filename=table.${format}`,
          `table.${format}`,
        );
      });
      expect(downloadAs).toHaveBeenCalledWith({ format });
      expect(toast).toHaveBeenCalledWith({
        title: `${label} download started`,
      });
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    },
  );

  it("keeps data URLs unchanged", async () => {
    downloadAs.mockResolvedValue({
      url: "data:text/csv;base64,YQ==",
      filename: "table",
    });
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalledWith(
        "data:text/csv;base64,YQ==",
        "table.csv",
      );
    });
  });

  it.each([
    {
      label: "CSV",
      sourceFormat: "csv" as const,
      sourceText: "name,value\nalpha,1\n",
      expectedText: "name,value\nalpha,1\n",
    },
    {
      label: "TSV",
      sourceFormat: "tsv" as const,
      sourceText: "name\tvalue\nalpha\t1\n",
      expectedText: "name\tvalue\nalpha\t1\n",
    },
    {
      label: "JSON",
      sourceFormat: "json" as const,
      sourceText: JSON.stringify([{ name: "alpha", value: 1 }]),
      expectedText: JSON.stringify([{ name: "alpha", value: 1 }], null, 2),
    },
    {
      label: "Markdown",
      sourceFormat: "json" as const,
      sourceText: JSON.stringify([{ name: "alpha", value: 1 }]),
      expectedText: jsonToMarkdown([{ name: "alpha", value: 1 }]),
    },
  ])(
    "copies $label with its existing conversion",
    async ({ label, sourceFormat, sourceText, expectedText }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          text: vi.fn().mockResolvedValue(sourceText),
        }),
      );
      renderExportActions();
      await openDialog();

      fireEvent.click(screen.getByRole("button", { name: `Copy ${label}` }));

      await waitFor(() => {
        expect(copyToClipboard).toHaveBeenCalledWith(expectedText);
      });
      expect(downloadAs).toHaveBeenCalledWith({ format: sourceFormat });
      expect(toast).toHaveBeenCalledWith({ title: "Copied to clipboard" });
      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      });
    },
  );

  it("shows the failure inside the affected format row", async () => {
    downloadAs.mockRejectedValueOnce(new Error("Kernel disconnected"));
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));

    const alert = await screen.findByRole("alert");
    expect(screen.getByTestId("export-row-json")).toContainElement(alert);
    expect(screen.getByTestId("export-row-csv")).not.toContainElement(alert);
  });

  it("shows download request failures inside the dialog", async () => {
    downloadAs.mockRejectedValueOnce(new Error("Kernel disconnected"));
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to download");
    expect(alert).toHaveTextContent("Kernel disconnected");
    expect(downloadByURL).not.toHaveBeenCalled();
  });

  it("shows file delivery failures inside the dialog", async () => {
    vi.mocked(downloadByURL).mockImplementationOnce(() => {
      throw new Error("Download blocked");
    });
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to download");
    expect(alert).toHaveTextContent("Download blocked");
  });

  it("shows fetch failures inside the dialog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        statusText: "Forbidden",
      }),
    );
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Copy CSV" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to copy to clipboard");
    expect(alert).toHaveTextContent("Forbidden");
  });

  it("shows clipboard failures inside the dialog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        text: vi.fn().mockResolvedValue("name\nalpha\n"),
      }),
    );
    vi.mocked(copyToClipboard).mockRejectedValueOnce(
      new Error("Clipboard permission denied"),
    );
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Copy CSV" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Failed to copy to clipboard");
    expect(alert).toHaveTextContent("Clipboard permission denied");
  });

  it("shows backend failures before success fields", async () => {
    downloadAs.mockResolvedValueOnce({
      url: "https://example.test/partial",
      filename: "partial",
      error: "Export was rejected",
    });
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Export was rejected");
    expect(downloadByURL).not.toHaveBeenCalled();
  });

  it("installs missing packages and retries the same action", async () => {
    downloadAs
      .mockResolvedValueOnce({
        url: "",
        filename: "",
        error: "Parquet export requires pyarrow.",
        missing_packages: ["pyarrow"],
      })
      .mockResolvedValueOnce({
        url: "https://example.test/export",
        filename: "table",
      });
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download Parquet" }));

    expect(
      await screen.findByText("Parquet export requires pyarrow."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download Parquet" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Install pyarrow" }));
    expect(mocks.handleInstallPackages).toHaveBeenCalledWith(
      ["pyarrow"],
      expect.any(Function),
    );

    const onInstall = mocks.handleInstallPackages.mock
      .calls[0][1] as () => void;
    onInstall();

    await waitFor(() => {
      expect(downloadAs).toHaveBeenCalledTimes(2);
      expect(downloadByURL).toHaveBeenCalledWith(
        "https://example.test/export?download=1&filename=table.parquet",
        "table.parquet",
      );
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("hides package details and installation in read mode", async () => {
    downloadAs.mockResolvedValueOnce({
      url: "",
      filename: "",
      error: "Install pyarrow to export Parquet.",
      missing_packages: ["pyarrow"],
    });
    renderExportActions({}, null, "read");
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download Parquet" }));

    expect(
      await screen.findByText(
        "Parquet export isn't available in this notebook",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("pyarrow")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Install/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("clears stale failures before a new action and after close", async () => {
    downloadAs.mockRejectedValueOnce(new Error("First failure"));
    renderExportActions();
    let dialog = await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("First failure");

    fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(downloadByURL).toHaveBeenCalled();
    });

    downloadAs.mockRejectedValueOnce(new Error("Second failure"));
    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Second failure",
    );

    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    dialog = await openDialog();
    expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ignores a late failure from an earlier action", async () => {
    let rejectFirst: (reason: Error) => void = () => undefined;
    downloadAs
      .mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectFirst = reject;
          }),
      )
      .mockResolvedValueOnce({
        url: "https://example.test/export",
        filename: "table",
      });
    renderExportActions();
    await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "Download JSON" }));
    await waitFor(() => {
      expect(downloadByURL).toHaveBeenCalled();
    });

    await act(async () => {
      rejectFirst(new Error("Late failure"));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("ignores a late failure after the dialog closes", async () => {
    let rejectDownload: (reason: Error) => void = () => undefined;
    downloadAs.mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          rejectDownload = reject;
        }),
    );
    renderExportActions();
    const dialog = await openDialog();

    fireEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    await openDialog();

    await act(async () => {
      rejectDownload(new Error("Late failure"));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("closes with the close button and restores trigger focus", async () => {
    renderExportActions();
    const trigger = screen.getByTestId("export-button");
    const dialog = await openDialog();

    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(trigger).toHaveFocus();
    });
  });

  it("closes with Escape and restores trigger focus", async () => {
    renderExportActions();
    const trigger = screen.getByTestId("export-button");
    trigger.focus();
    const dialog = await openDialog();
    const closeButton = within(dialog).getByRole("button", { name: "Close" });
    closeButton.focus();

    fireEvent.keyDown(closeButton, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(trigger).toHaveFocus();
    });
  });

  it.each([
    {
      name: "the size check is pending",
      props: { sizeBytesIsLoading: true },
    },
    {
      name: "the export is over the host limit",
      props: { sizeBytes: 101 },
    },
  ])("keeps the trigger disabled when $name", ({ props }) => {
    renderExportActions(props, {
      limitBytes: 100,
      unavailableMessage: "This export is too large.",
    });
    const trigger = screen.getByTestId("export-button");

    expect(trigger).toBeDisabled();
    expect(trigger).toHaveClass("print:hidden");
    expect(trigger.parentElement).toHaveAttribute("tabindex", "0");
    fireEvent.click(trigger);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

const LONG_GEOMETRY_WKT = `LINESTRING (${Array.from(
  { length: 160 },
  (_, index) => `${index} ${index % 17}`,
).join(", ")})`;
const jsonRows = [{ row_label: "long", geometry: LONG_GEOMETRY_WKT }];

describe("ExportActions clipboard geometry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    downloadAs.mockResolvedValue({
      url: "https://example.test/export",
      filename: "geometry",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    {
      label: "CSV",
      sourceFormat: "csv" as const,
      sourceText: `row_label,geometry\nlong,"${LONG_GEOMETRY_WKT}"\n`,
      expectedText: `row_label,geometry\nlong,"${LONG_GEOMETRY_WKT}"\n`,
    },
    {
      label: "TSV",
      sourceFormat: "tsv" as const,
      sourceText: `row_label\tgeometry\nlong\t${LONG_GEOMETRY_WKT}\n`,
      expectedText: `row_label\tgeometry\nlong\t${LONG_GEOMETRY_WKT}\n`,
    },
    {
      label: "JSON",
      sourceFormat: "json" as const,
      sourceText: JSON.stringify(jsonRows),
      expectedText: JSON.stringify(jsonRows, null, 2),
    },
    {
      label: "Markdown",
      sourceFormat: "json" as const,
      sourceText: JSON.stringify(jsonRows),
      expectedText: jsonToMarkdown(jsonRows),
    },
  ])(
    "copies complete geometry text as $label",
    async ({ label, sourceFormat, sourceText, expectedText }) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          text: vi.fn().mockResolvedValue(sourceText),
        }),
      );
      renderExportActions();
      await openDialog();

      fireEvent.click(screen.getByRole("button", { name: `Copy ${label}` }));

      await waitFor(() => {
        expect(copyToClipboard).toHaveBeenCalledWith(expectedText);
      });
      expect(downloadAs).toHaveBeenCalledWith({ format: sourceFormat });
    },
  );
});
