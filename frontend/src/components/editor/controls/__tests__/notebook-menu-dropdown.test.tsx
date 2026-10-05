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
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  type DetectedDataSource,
  invalidateDataSourceDiscovery,
} from "@/core/datasets/data-source-discovery";
import { DiscoverDataSources } from "@/core/datasets/request-registry";
import { layoutStateAtom } from "@/core/layout/state";
import { kioskModeAtom, viewStateAtom } from "@/core/mode";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { isWasm } from "@/core/wasm/utils";
import { WebSocketState } from "@/core/websocket/types";
import {
  DEFAULT_EXPORT_OPTIONS,
  exportOptionsAtom,
  lastExportFormatAtom,
} from "../../actions/export-dialog/state";
import CommandPalette from "../command-palette";
import { NotebookMenuDropdown } from "../notebook-menu-dropdown";
import { commandPaletteAtom } from "../state";

const POSTGRES_SOURCE: DetectedDataSource = {
  id: "postgres-libpq-environment",
  integration: "postgres",
  category: "database",
  displayName: "PostgreSQL",
  confidence: "high",
  origins: [{ type: "environment", label: "Kernel environment" }],
  configuration: [],
  code: "engine = create_engine()",
  hidesWhen: { kind: "dialect", substrings: ["postgres"] },
};

const S3_SOURCE: DetectedDataSource = {
  id: "aws-s3-environment",
  integration: "aws",
  category: "object-storage",
  displayName: "AWS S3",
  confidence: "high",
  origins: [{ type: "environment", label: "Kernel environment" }],
  configuration: [],
  code: "storage = create_s3_storage()",
  hidesWhen: {
    kind: "storage",
    protocols: ["s3"],
    backendTypes: ["s3"],
  },
};

vi.mock("@/core/wasm/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/core/wasm/utils")>();
  return { ...actual, isWasm: vi.fn(() => false) };
});

global.HTMLElement.prototype.scrollIntoView = () => {
  // jsdom does not implement scrollIntoView; cmdk calls it on selection.
};

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <Provider store={store}>
      <TooltipProvider>
        <ModalProvider>{children}</ModalProvider>
      </TooltipProvider>
    </Provider>
  );
}

function openNotebookMenu() {
  fireEvent.pointerDown(screen.getByTestId("notebook-menu-dropdown"), {
    button: 0,
    ctrlKey: false,
  });
}

function renderNotebookControls() {
  return render(
    <>
      <NotebookMenuDropdown />
      <CommandPalette />
    </>,
    { wrapper },
  );
}

async function selectDownloadCommand(name: string) {
  act(() => store.set(commandPaletteAtom, true));
  fireEvent.click(await screen.findByText(`Download > ${name}`));
}

describe("NotebookMenuDropdown", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(filenameAtom, "/project/notebook.py");
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(connectionAtom, { state: WebSocketState.OPEN });
    store.set(kioskModeAtom, false);
    store.set(layoutStateAtom, {
      selectedLayout: "vertical",
      layoutData: {},
    });
    store.set(exportOptionsAtom, DEFAULT_EXPORT_OPTIONS);
    store.set(lastExportFormatAtom, "html");
    store.set(commandPaletteAtom, false);
    vi.mocked(isWasm).mockReturnValue(false);
    vi.stubGlobal("PointerEvent", MouseEvent);
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    invalidateDataSourceDiscovery();
    vi.spyOn(DiscoverDataSources, "request").mockResolvedValue({
      request_id: "request-id",
      sources: [],
    });
  });

  afterEach(() => {
    document.title = "";
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows detected databases in the add connection submenu", async () => {
    vi.mocked(DiscoverDataSources.request).mockResolvedValue({
      request_id: "request-id",
      sources: [POSTGRES_SOURCE],
    });

    render(<NotebookMenuDropdown />, { wrapper });
    await waitFor(() =>
      expect(DiscoverDataSources.request).toHaveBeenCalledOnce(),
    );
    await act(async () => Promise.resolve());
    openNotebookMenu();
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Add database connection" }),
    );

    const suggestion = await screen.findByRole("menuitem", {
      name: "Add PostgreSQL",
    });
    const browseAll = screen.getByRole("menuitem", {
      name: "Browse all connections",
    });
    expect(suggestion).toBeVisible();
    expect(browseAll).toBeVisible();
    expect(
      suggestion.compareDocumentPosition(browseAll) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("shows detected storage in the add remote storage submenu", async () => {
    vi.mocked(DiscoverDataSources.request).mockResolvedValue({
      request_id: "request-id",
      sources: [S3_SOURCE],
    });

    render(<NotebookMenuDropdown />, { wrapper });
    await waitFor(() =>
      expect(DiscoverDataSources.request).toHaveBeenCalledOnce(),
    );
    await act(async () => Promise.resolve());
    openNotebookMenu();
    fireEvent.click(
      await screen.findByRole("menuitem", { name: "Add remote storage" }),
    );

    const suggestion = await screen.findByRole("menuitem", {
      name: "Add AWS S3",
    });
    const browseAll = screen.getByRole("menuitem", {
      name: "Browse all connections",
    });
    expect(suggestion).toBeVisible();
    expect(browseAll).toBeVisible();
    expect(
      suggestion.compareDocumentPosition(browseAll) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("returns focus to the notebook menu when the dialog closes", async () => {
    render(<NotebookMenuDropdown />, { wrapper });
    const menuButton = screen.getByTestId("notebook-menu-dropdown");

    openNotebookMenu();
    fireEvent.click(
      await screen.findByRole("menuitem", {
        name: "Export…",
      }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Close" }));

    await waitFor(() => expect(menuButton).toHaveFocus());
  });

  it("hides the download menu but keeps its command palette actions", async () => {
    renderNotebookControls();

    openNotebookMenu();
    expect(
      screen.queryByRole("menuitem", { name: "Download" }),
    ).not.toBeInTheDocument();

    act(() => store.set(commandPaletteAtom, true));
    expect(await screen.findByText("Download > Download as PNG")).toBeVisible();
  });

  it("opens the HTML shortcut with code excluded", async () => {
    renderNotebookControls();

    await selectDownloadCommand("Download as HTML (exclude code)");

    expect(await screen.findByTestId("export-dialog")).toBeVisible();
    expect(screen.getByTestId("export-format-html")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("switch", { name: "Include code" }),
    ).not.toBeChecked();
  });

  it("opens the slides PDF shortcut with the slides layout", async () => {
    store.set(layoutStateAtom, {
      selectedLayout: "slides",
      layoutData: {},
    });
    renderNotebookControls();

    await selectDownloadCommand("Download as PDF > Slides Layout");

    expect(await screen.findByTestId("export-dialog")).toBeVisible();
    expect(screen.getByTestId("export-format-pdf")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("radio", { name: "Slides" })).toBeChecked();
  });

  it("hides the slides PDF shortcut in WebAssembly", async () => {
    vi.mocked(isWasm).mockReturnValue(true);
    store.set(layoutStateAtom, {
      selectedLayout: "slides",
      layoutData: {},
    });
    renderNotebookControls();

    act(() => store.set(commandPaletteAtom, true));

    expect(
      await screen.findByText("Download > Download as PDF > Document Layout"),
    ).toBeVisible();
    expect(
      screen.queryByText("Download > Download as PDF > Slides Layout"),
    ).not.toBeInTheDocument();
  });

  it("preselects each Python format from its download shortcut", async () => {
    renderNotebookControls();

    await selectDownloadCommand("Download notebook source");

    expect(await screen.findByTestId("export-dialog")).toBeVisible();
    expect(screen.getByTestId("export-format-script")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("radio", { name: "Notebook source" }),
    ).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() =>
      expect(screen.queryByTestId("export-dialog")).not.toBeInTheDocument(),
    );

    await selectDownloadCommand("Download flat script");

    expect(await screen.findByTestId("export-dialog")).toBeVisible();
    expect(screen.getByRole("radio", { name: "Flat script" })).toBeChecked();
  });
});
