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

  return render(
    <Provider store={store}>
      <TooltipProvider delayDuration={0}>
        <ExportActions downloadAs={downloadAs} {...props} />
      </TooltipProvider>
    </Provider>,
  );
}

async function openDialog() {
  fireEvent.click(screen.getByTestId("export-button"));
  return screen.findByRole("dialog", { name: "Export table" });
}

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

  it("shows formats in the approved order with reserved disclosure space", async () => {
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
    for (const row of rows) {
      expect(row.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
    }
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
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    },
  );

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

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Parquet export requires pyarrow.");
    fireEvent.click(
      within(alert).getByRole("button", { name: "Install pyarrow" }),
    );
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

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Parquet export isn't available in this notebook",
    );
    expect(alert).not.toHaveTextContent("pyarrow");
    expect(within(alert).queryByRole("button")).not.toBeInTheDocument();
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

    fireEvent.click(within(dialog).getByText("Close", { selector: "button" }));
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
    fireEvent.click(within(dialog).getByText("Close", { selector: "button" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    await openDialog();

    await act(async () => {
      rejectDownload(new Error("Late failure"));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("closes with the footer action and restores trigger focus", async () => {
    renderExportActions();
    const trigger = screen.getByTestId("export-button");
    const dialog = await openDialog();

    fireEvent.click(within(dialog).getByText("Close", { selector: "button" }));

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
    const closeButton = within(dialog).getByText("Close", {
      selector: "button",
    });
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
