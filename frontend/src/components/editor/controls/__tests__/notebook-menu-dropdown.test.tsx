/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { layoutStateAtom } from "@/core/layout/layout";
import { kioskModeAtom, viewStateAtom } from "@/core/mode";
import { requestClientAtom } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import {
  DEFAULT_EXPORT_OPTIONS,
  exportOptionsAtom,
  lastExportFormatAtom,
} from "../../actions/export-dialog/state";
import { NotebookMenuDropdown } from "../notebook-menu-dropdown";

vi.mock("@/core/wasm/utils", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/core/wasm/utils")>();
  return { ...actual, isWasm: vi.fn(() => false) };
});

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

async function openDownloadMenu() {
  openNotebookMenu();
  fireEvent.click(await screen.findByRole("menuitem", { name: "Download" }));
}

async function selectDownload(name: string | RegExp) {
  await openDownloadMenu();
  fireEvent.click(await screen.findByRole("menuitem", { name }));
}

describe("NotebookMenuDropdown", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    store.set(requestClientAtom, MockRequestClient.create());
    store.set(filenameAtom, "/project/notebook.py");
    store.set(viewStateAtom, { mode: "edit", cellAnchor: null });
    store.set(kioskModeAtom, false);
    store.set(layoutStateAtom, {
      selectedLayout: "vertical",
      layoutData: {},
    });
    store.set(exportOptionsAtom, DEFAULT_EXPORT_OPTIONS);
    store.set(lastExportFormatAtom, "html");
    vi.stubGlobal("PointerEvent", MouseEvent);
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  afterEach(() => {
    document.title = "";
    vi.unstubAllGlobals();
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

  it("opens the HTML shortcut with code excluded", async () => {
    render(<NotebookMenuDropdown />, { wrapper });

    await selectDownload("Download as HTML (exclude code)");

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
    render(<NotebookMenuDropdown />, { wrapper });

    await openDownloadMenu();
    fireEvent.click(
      await screen.findByRole("menuitem", {
        name: "Download as PDF",
      }),
    );
    fireEvent.click(
      await screen.findByRole("menuitem", {
        name: /Slides Layout/,
      }),
    );

    expect(await screen.findByTestId("export-dialog")).toBeVisible();
    expect(screen.getByTestId("export-format-pdf")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("radio", { name: "Slides" })).toBeChecked();
  });

  it("preselects each Python format from its download shortcut", async () => {
    render(<NotebookMenuDropdown />, { wrapper });

    await selectDownload("Download notebook source");

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

    await selectDownload("Download flat script");

    expect(await screen.findByTestId("export-dialog")).toBeVisible();
    expect(screen.getByRole("radio", { name: "Flat script" })).toBeChecked();
  });
});
