/* Copyright 2026 Marimo. All rights reserved. */

import { render, screen } from "@testing-library/react";
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
});
