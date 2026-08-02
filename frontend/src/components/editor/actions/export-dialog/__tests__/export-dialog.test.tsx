/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { Dialog } from "@/components/ui/dialog";
import { TooltipProvider } from "@/components/ui/tooltip";
import { viewStateAtom } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { isWasm } from "@/core/wasm/utils";
import * as copyModule from "@/utils/copy";
import { ExportDialog } from "../export-dialog";
import {
  DEFAULT_EXPORT_OPTIONS,
  type ExportFormat,
  exportOptionsAtom,
  lastExportFormatAtom,
} from "../state";

const { exportNotebookMock } = vi.hoisted(() => ({
  exportNotebookMock: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/core/wasm/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/core/wasm/utils")>();
  return { ...actual, isWasm: vi.fn(() => false) };
});

vi.mock("../export-notebook", () => ({
  exportNotebook: exportNotebookMock,
}));

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <TooltipProvider>
        <Dialog open={true}>{children}</Dialog>
      </TooltipProvider>
    </Provider>
  );
}

function renderDialog(initialFormat?: ExportFormat, onClose = vi.fn()) {
  return render(
    <ExportDialog initialFormat={initialFormat} onClose={onClose} />,
    { wrapper },
  );
}

async function waitForExportEnabled() {
  await waitFor(() =>
    expect(screen.getByTestId("export-submit")).toBeEnabled(),
  );
}

describe("ExportDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(filenameAtom, "/project/notebook.py");
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(exportOptionsAtom, DEFAULT_EXPORT_OPTIONS);
    store.set(lastExportFormatAtom, "html");
    vi.mocked(isWasm).mockReturnValue(false);
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("locks format and option controls while exporting", async () => {
    let finishExport: (() => void) | undefined;
    exportNotebookMock.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finishExport = resolve;
        }),
    );
    const onClose = vi.fn();
    renderDialog("pdf", onClose);
    await waitForExportEnabled();

    fireEvent.click(screen.getByTestId("export-submit"));
    await waitFor(() => expect(exportNotebookMock).toHaveBeenCalledOnce());

    expect(screen.getByTestId("export-submit")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(screen.getByTestId("export-format-html")).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Document" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Include code" })).toBeDisabled();

    finishExport?.();
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });

  it("describes the selected PDF options", async () => {
    renderDialog("pdf");
    await waitForExportEnabled();

    expect(
      screen.getByRole("radiogroup", { name: "Layout" }),
    ).toHaveAccessibleDescription("Creates pages for reading or printing.");
    expect(
      screen.getByRole("switch", { name: "Include code" }),
    ).toHaveAccessibleDescription("Includes code cells in the PDF.");
    const method = screen.getByRole("radiogroup", { name: "Method" });
    expect(method).toHaveAccessibleDescription(
      "Uses browser rendering to preserve the notebook's visual output.",
    );
    expect(screen.getByRole("radio", { name: "Browser" })).toBeChecked();

    fireEvent.click(screen.getByRole("radio", { name: "LaTeX first" }));
    expect(method).toHaveAccessibleDescription(
      "Uses Pandoc and TeX when available, then falls back to browser rendering.",
    );
    expect(screen.getByRole("radio", { name: "LaTeX first" })).toBeChecked();

    fireEvent.click(screen.getByRole("switch", { name: "Include code" }));
    expect(
      screen.getByRole("switch", { name: "Include code" }),
    ).toHaveAccessibleDescription("Leaves code cells out of the PDF.");

    fireEvent.click(screen.getByRole("radio", { name: "Slides" }));
    expect(
      screen.getByRole("radiogroup", { name: "Layout" }),
    ).toHaveAccessibleDescription(
      "Creates presentation slides from the notebook.",
    );
  });

  it("describes the selected Markdown format", () => {
    renderDialog("markdown");

    expect(
      screen.getByRole("combobox", { name: "Format" }),
    ).toHaveAccessibleDescription(
      "Chooses a format from the notebook filename. Defaults to Markdown (.md).",
    );

    act(() => {
      store.set(exportOptionsAtom, {
        ...store.get(exportOptionsAtom),
        markdown: { flavor: "qmd" },
      });
    });

    expect(
      screen.getByRole("combobox", { name: "Format" }),
    ).toHaveAccessibleDescription("Creates a .qmd file for Quarto.");
  });

  it("describes the selected Jupyter cell order", () => {
    renderDialog("ipynb");

    expect(
      screen.getByRole("radiogroup", { name: "Cell order" }),
    ).toHaveAccessibleDescription(
      "Reorders cells so each cell appears after the cells it depends on.",
    );

    fireEvent.click(screen.getByRole("radio", { name: "Top to bottom" }));

    expect(
      screen.getByRole("radiogroup", { name: "Cell order" }),
    ).toHaveAccessibleDescription(
      "Keeps cells in the same order as this notebook.",
    );
  });

  it("shows every format and updates the equivalent command with options", async () => {
    renderDialog();

    for (const format of [
      "html",
      "markdown",
      "ipynb",
      "pdf",
      "script",
      "png",
    ]) {
      expect(screen.getByTestId(`export-format-${format}`)).toBeVisible();
    }

    await waitForExportEnabled();
    expect(screen.getByTestId("export-cli-command")).toHaveTextContent(
      "marimo export html /project/notebook.py --include-code",
    );
    expect(
      screen.getByText(
        "Uses the current session state. The copied command exports the saved notebook.",
      ),
    ).toBeVisible();

    fireEvent.click(screen.getByRole("switch", { name: "Include code" }));
    expect(screen.getByTestId("export-cli-command")).toHaveTextContent(
      "--no-include-code",
    );
  });

  it("matches tab keyboard orientation to the responsive layout", () => {
    const listeners = new Set<() => void>();
    const media = {
      matches: false,
      addEventListener: vi.fn((_event: "change", listener: () => void) =>
        listeners.add(listener),
      ),
      removeEventListener: vi.fn((_event: "change", listener: () => void) =>
        listeners.delete(listener),
      ),
    };
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => media),
    );

    renderDialog();
    const tablist = screen.getByRole("tablist", { name: "Export format" });
    expect(tablist).toHaveAttribute("aria-orientation", "horizontal");

    act(() => {
      media.matches = true;
      for (const listener of listeners) {
        listener();
      }
    });
    expect(tablist).toHaveAttribute("aria-orientation", "vertical");
  });

  it("keeps unavailable formats visible and names missing packages", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getExportAvailability: vi.fn().mockResolvedValue({
          source: "server",
          formats: [
            {
              format: "pdf",
              dependenciesAvailable: false,
              missingPackages: ["nbconvert[webpdf]"],
            },
          ],
        }),
      }),
    );

    renderDialog("pdf");

    expect(await screen.findByText("nbconvert[webpdf]")).toBeVisible();
    expect(
      screen.getByText(/where marimo is running to use this export/),
    ).toBeVisible();
    expect(screen.getByTestId("export-submit")).toBeDisabled();
    expect(screen.getByTestId("export-format-pdf")).toBeVisible();
  });

  it("announces requirement checks as status updates", () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getExportAvailability: vi.fn(() => new Promise(() => undefined)),
      }),
    );

    renderDialog("pdf");

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking PDF requirements…",
    );
  });

  it("hides the document renderer when exporting slides", async () => {
    renderDialog("pdf");
    await waitForExportEnabled();

    fireEvent.click(screen.getByRole("radio", { name: "Slides" }));

    expect(
      screen.queryByRole("radiogroup", { name: "Method" }),
    ).not.toBeInTheDocument();
  });

  it("requires a saved file for notebook source but not flat script", () => {
    store.set(filenameAtom, null);

    renderDialog("script");

    expect(
      screen.getByText("Name and save this notebook before exporting."),
    ).toBeVisible();
    expect(screen.getByTestId("export-submit")).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: "Flat script" }));

    expect(
      screen.queryByText("Name and save this notebook before exporting."),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("export-submit")).toBeEnabled();
  });

  it("allows an export attempt when requirements cannot be checked", async () => {
    store.set(
      requestClientAtom,
      MockRequestClient.create({
        getExportAvailability: vi
          .fn()
          .mockRejectedValue(new Error("unavailable")),
      }),
    );

    renderDialog("pdf");

    expect(
      await screen.findByText(
        "Couldn't check whether this export is available. You can still try it.",
      ),
    ).toBeVisible();
    expect(screen.getByTestId("export-submit")).toBeEnabled();
  });

  it("shows browser printing for PDF export in WebAssembly", () => {
    vi.mocked(isWasm).mockReturnValue(true);

    renderDialog("pdf");

    expect(
      screen.getByText(
        "Use your browser's print dialog to save the current app view as a PDF.",
      ),
    ).toBeVisible();
    expect(screen.queryByRole("radio", { name: "Document" })).toBeNull();
    expect(screen.queryByTestId("export-cli-command")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Print to PDF" })).toBeEnabled();
  });

  it("copies the displayed CLI command", async () => {
    store.set(exportOptionsAtom, {
      ...DEFAULT_EXPORT_OPTIONS,
      script: { type: "flat" },
    });
    renderDialog("script");
    await waitForExportEnabled();

    fireEvent.click(
      screen.getByRole("button", { name: "Copy POSIX shell command" }),
    );

    await waitFor(() =>
      expect(copyModule.copyToClipboard).toHaveBeenCalledWith(
        "marimo export script /project/notebook.py -o /project/notebook.script.py",
      ),
    );
  });

  it("describes and selects each Python format", () => {
    renderDialog("script");

    expect(
      screen.getByRole("radio", { name: "Notebook source" }),
    ).toBeChecked();
    expect(
      screen.getByRole("radiogroup", { name: "Format" }),
    ).toHaveAccessibleDescription(
      "Downloads the saved notebook source for continued editing in marimo.",
    );
    expect(
      screen.getByRole("button", { name: "Export notebook source" }),
    ).toBeVisible();
    expect(screen.queryByTestId("export-cli-command")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "Flat script" }));

    expect(
      screen.getByRole("radiogroup", { name: "Format" }),
    ).toHaveAccessibleDescription(
      "Reorders cells so the Python script runs from top to bottom.",
    );
    expect(
      screen.getByRole("button", { name: "Export flat script" }),
    ).toBeVisible();
    expect(screen.getByTestId("export-cli-command")).toHaveTextContent(
      "marimo export script /project/notebook.py",
    );
  });

  it("hides the shell command until the notebook is saved", () => {
    store.set(filenameAtom, null);
    store.set(exportOptionsAtom, {
      ...DEFAULT_EXPORT_OPTIONS,
      script: { type: "flat" },
    });

    renderDialog("script");

    expect(screen.queryByTestId("export-cli-command")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Save the notebook to copy an equivalent shell command.",
      ),
    ).toBeVisible();
  });
});
