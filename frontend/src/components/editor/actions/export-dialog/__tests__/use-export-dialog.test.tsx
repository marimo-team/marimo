/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { kioskModeAtom, viewStateAtom } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { isWasm } from "@/core/wasm/utils";
import {
  DEFAULT_EXPORT_OPTIONS,
  type ExportFormat,
  exportOptionsAtom,
  lastExportFormatAtom,
} from "../state";
import { useExportDialog } from "../use-export-dialog";

const { downloadHTMLAsImageMock, exportNotebookMock, toastMock } = vi.hoisted(
  () => ({
    downloadHTMLAsImageMock: vi.fn().mockResolvedValue(true),
    exportNotebookMock: vi.fn().mockResolvedValue(undefined),
    toastMock: vi.fn(() => ({
      dismiss: vi.fn(),
      update: vi.fn(),
    })),
  }),
);

vi.mock("@/components/ui/use-toast", () => ({
  toast: toastMock,
}));

vi.mock("@/core/wasm/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/core/wasm/utils")>();
  return { ...actual, isWasm: vi.fn(() => false) };
});

vi.mock("@/utils/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/download")>();
  return { ...actual, downloadHTMLAsImage: downloadHTMLAsImageMock };
});

vi.mock("../export-notebook", () => ({
  exportNotebook: exportNotebookMock,
}));

function wrapper({ children }: { children: React.ReactNode }) {
  return <Provider store={store}>{children}</Provider>;
}

function renderController(initialFormat?: ExportFormat, onClose = vi.fn()) {
  return renderHook(() => useExportDialog({ initialFormat, onClose }), {
    wrapper,
  });
}

async function waitForAvailable(
  getController: () => ReturnType<typeof useExportDialog>,
) {
  await waitFor(() =>
    expect(getController().selected.status.available).toBe(true),
  );
}

describe("useExportDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(filenameAtom, "/project/notebook.py");
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(kioskModeAtom, false);
    store.set(exportOptionsAtom, DEFAULT_EXPORT_OPTIONS);
    store.set(lastExportFormatAtom, "html");
    vi.mocked(isWasm).mockReturnValue(false);
    document.title = "Notebook";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.getElementById("App")?.remove();
  });

  it("keeps PNG export open when the app view is missing", async () => {
    exportNotebookMock.mockImplementationOnce(
      async ({ capturePNG }: { capturePNG: () => Promise<void> }) =>
        capturePNG(),
    );
    const onClose = vi.fn();
    const { result } = renderController("png", onClose);
    await waitForAvailable(() => result.current);

    await act(async () => {
      await result.current.submit();
    });

    expect(toastMock).toHaveBeenCalledWith({
      title: "Failed to download as PNG",
      description: "The current app view could not be captured.",
      variant: "danger",
    });
    expect(result.current.isExporting).toBe(false);
    expect(store.get(viewStateAtom).mode).toBe("edit");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("captures the app view and restores the dialog", async () => {
    const app = document.createElement("div");
    app.id = "App";
    document.body.append(app);
    const dialogContainer = document.createElement("div");
    const dialog = document.createElement("div");
    dialogContainer.append(dialog);
    document.body.append(dialogContainer);
    exportNotebookMock.mockImplementationOnce(
      async ({ capturePNG }: { capturePNG: () => Promise<void> }) =>
        capturePNG(),
    );
    downloadHTMLAsImageMock.mockImplementationOnce(
      async ({ prepare }: Parameters<typeof downloadHTMLAsImageMock>[0]) => {
        const cleanup = prepare?.(app);
        expect(dialogContainer).not.toBeVisible();
        cleanup?.();
        return true;
      },
    );
    const onClose = vi.fn();
    const { result } = renderController("png", onClose);
    await waitForAvailable(() => result.current);
    act(() => {
      result.current.dialogRef.current = dialog;
    });

    await act(async () => {
      await result.current.submit();
    });

    expect(onClose).toHaveBeenCalledOnce();
    expect(store.get(viewStateAtom).mode).toBe("edit");
    expect(dialogContainer).toBeVisible();
    dialogContainer.remove();
  });

  it("restores the dialog and edit mode when PNG capture fails", async () => {
    const app = document.createElement("div");
    app.id = "App";
    document.body.append(app);
    const dialogContainer = document.createElement("div");
    const dialog = document.createElement("div");
    dialogContainer.append(dialog);
    document.body.append(dialogContainer);
    exportNotebookMock.mockImplementationOnce(
      async ({ capturePNG }: { capturePNG: () => Promise<void> }) =>
        capturePNG(),
    );
    downloadHTMLAsImageMock.mockImplementationOnce(
      async ({ prepare }: Parameters<typeof downloadHTMLAsImageMock>[0]) => {
        const cleanup = prepare?.(app);
        cleanup?.();
        return false;
      },
    );
    const onClose = vi.fn();
    const { result } = renderController("png", onClose);
    await waitForAvailable(() => result.current);
    act(() => {
      result.current.dialogRef.current = dialog;
    });

    await act(async () => {
      await result.current.submit();
    });

    expect(result.current.isExporting).toBe(false);
    expect(store.get(viewStateAtom).mode).toBe("edit");
    expect(dialogContainer).toBeVisible();
    expect(onClose).not.toHaveBeenCalled();
    dialogContainer.remove();
  });

  it("does not close a newer modal after unmounting", async () => {
    let finishExport: (() => void) | undefined;
    exportNotebookMock.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finishExport = resolve;
        }),
    );
    const onClose = vi.fn();
    const { result, unmount } = renderController(undefined, onClose);
    await waitForAvailable(() => result.current);

    let submit: Promise<void> | undefined;
    act(() => {
      submit = result.current.submit();
    });
    await waitFor(() => expect(exportNotebookMock).toHaveBeenCalledOnce());

    unmount();
    finishExport?.();
    await submit;

    expect(onClose).not.toHaveBeenCalled();
  });

  it("keeps the dialog open when a server export fails", async () => {
    exportNotebookMock.mockRejectedValueOnce(new Error("export failed"));
    const onClose = vi.fn();
    const { result } = renderController(undefined, onClose);
    await waitForAvailable(() => result.current);

    await act(async () => {
      await result.current.submit();
    });

    expect(result.current.isExporting).toBe(false);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("uses the saved notebook filename for source export", async () => {
    store.set(filenameAtom, "/project/saved-name.py");
    document.title = "Custom app title";
    const { result } = renderController("script");
    await waitForAvailable(() => result.current);

    await act(async () => {
      await result.current.submit();
    });

    expect(exportNotebookMock).toHaveBeenCalledWith(
      expect.objectContaining({ sourceFilename: "saved-name.py" }),
    );
  });

  it("persists the selected format and its options", () => {
    const first = renderController();

    act(() => {
      first.result.current.selectFormat("pdf");
      first.result.current.updateOptions("pdf", { preset: "slides" });
    });
    first.unmount();

    const second = renderController();
    expect(second.result.current.selected.format).toBe("pdf");
    expect(second.result.current.options.pdf.preset).toBe("slides");
  });

  it("prints the current view for PDF export in WebAssembly", async () => {
    vi.mocked(isWasm).mockReturnValue(true);
    const print = vi.fn();
    vi.stubGlobal("print", print);
    const onClose = vi.fn();
    const { result } = renderController("pdf", onClose);

    expect(result.current.selected.usesBrowserPrint).toBe(true);

    await act(async () => {
      await result.current.submit();
    });

    expect(onClose).toHaveBeenCalledOnce();
    await waitFor(() => expect(print).toHaveBeenCalledOnce());
    expect(exportNotebookMock).not.toHaveBeenCalled();
  });
});
