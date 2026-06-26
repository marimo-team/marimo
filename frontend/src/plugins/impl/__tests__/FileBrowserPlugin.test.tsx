/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import type { IPluginProps } from "../../types";
import { FileBrowserPlugin } from "../FileBrowserPlugin";

interface MockFile {
  id: string;
  path: string;
  name: string;
  is_directory: boolean;
}

const FILES: MockFile[] = [
  { id: "1", path: "/home/user/docs", name: "docs", is_directory: true },
  { id: "2", path: "/home/user/a.txt", name: "a.txt", is_directory: false },
  { id: "3", path: "/home/user/b.txt", name: "b.txt", is_directory: false },
];

type Value = MockFile[];

function makeProps(
  overrides: {
    selectionMode?: string;
    multiple?: boolean;
    value?: Value;
    setValue?: (v: Value) => void;
    files?: MockFile[];
  } = {},
): IPluginProps<Value, Record<string, unknown>> {
  const files = overrides.files ?? FILES;
  return {
    data: {
      initialPath: "/home/user",
      filetypes: [],
      selectionMode: overrides.selectionMode ?? "all",
      multiple: overrides.multiple ?? true,
      label: null,
      restrictNavigation: false,
    },
    value: overrides.value ?? [],
    setValue: overrides.setValue ?? vi.fn(),
    host: document.createElement("div"),
    functions: {
      list_directory: vi.fn().mockResolvedValue({
        files,
        total_count: files.length,
        is_truncated: false,
      }),
    },
  } as unknown as IPluginProps<Value, Record<string, unknown>>;
}

function renderBrowser(overrides: Parameters<typeof makeProps>[0] = {}) {
  return render(
    FileBrowserPlugin.render(
      makeProps(overrides) as Parameters<typeof FileBrowserPlugin.render>[0],
    ),
  );
}

beforeAll(() => {
  SetupMocks.resizeObserver();
  store.set(initialModeAtom, "edit");
});

describe("FileBrowserPlugin keyboard accessibility", () => {
  it("renders a row per file plus the parent row", async () => {
    renderBrowser();
    expect(await screen.findByText("docs")).toBeInTheDocument();
    // parent "..", docs, a.txt, b.txt
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("marks the list as a multiselectable grid", async () => {
    renderBrowser({ multiple: true });
    await screen.findByText("docs");
    const grid = screen.getByRole("grid");
    expect(grid).toHaveAttribute("aria-multiselectable", "true");
  });

  it("does not select a non-selectable file on click (mode=directory)", async () => {
    const setValue = vi.fn();
    renderBrowser({ selectionMode: "directory", setValue });
    const fileCell = await screen.findByText("a.txt");
    fireEvent.click(fileCell.closest('[role="row"]')!);
    expect(setValue).not.toHaveBeenCalled();
  });

  it("labels each selectable checkbox with the file name", async () => {
    renderBrowser({ selectionMode: "all" });
    await screen.findByText("docs");
    expect(
      screen.getByRole("checkbox", { name: "Select a.txt" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: "Select docs" }),
    ).toBeInTheDocument();
  });

  it("keeps checkboxes out of the tab order", async () => {
    renderBrowser({ selectionMode: "all" });
    await screen.findByText("docs");
    expect(
      screen.getByRole("checkbox", { name: "Select a.txt" }),
    ).toHaveAttribute("tabindex", "-1");
  });

  it("places exactly one row in the tab order", async () => {
    renderBrowser();
    await screen.findByText("docs");
    const rows = screen.getAllByRole("row");
    const tabbable = rows.filter((r) => r.getAttribute("tabindex") === "0");
    expect(tabbable).toHaveLength(1);
    // the parent row is first and starts active
    expect(rows[0]).toHaveAttribute("tabindex", "0");
  });

  it("resets the active row to the parent row after navigating", async () => {
    renderBrowser({ selectionMode: "all" });
    const docs = await screen.findByText("docs");
    const docsRow = docs.closest('[role="row"]')!;
    fireEvent.keyDown(docsRow, { key: "ArrowDown" }); // move active off the parent
    fireEvent.click(docs); // navigate into "docs"
    await screen.findByText("docs"); // listing reloads (mock returns same files)
    const rows = screen.getAllByRole("row");
    expect(rows[0]).toHaveAttribute("tabindex", "0");
  });
});
