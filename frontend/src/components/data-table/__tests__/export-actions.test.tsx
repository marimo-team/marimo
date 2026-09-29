/* Copyright 2026 Marimo. All rights reserved. */

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { downloadSizeLimitAtom } from "../download-policy/atoms";
import { ExportActions, type ExportActionProps } from "../export-actions";

const downloadAs = vi.fn<ExportActionProps["downloadAs"]>();

function renderExportActions(
  props: Partial<ExportActionProps> = {},
  sizeLimit: { limitBytes: number; unavailableMessage: string } | null = null,
) {
  const store = createStore();
  store.set(downloadSizeLimitAtom, sizeLimit);

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

  it("closes with the footer action and restores trigger focus", async () => {
    renderExportActions();
    const trigger = screen.getByTestId("export-button");
    trigger.focus();
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
