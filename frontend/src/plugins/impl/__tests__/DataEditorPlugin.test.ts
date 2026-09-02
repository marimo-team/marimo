/* Copyright 2026 Marimo. All rights reserved. */

import React, { Suspense } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import type { IPluginProps } from "../../types";
import type { EditorRow, Edits } from "../data-editor/types";
import { DataEditorPlugin } from "../DataEditorPlugin";

type PluginData = z.infer<typeof DataEditorPlugin.validator>;

const mocks = vi.hoisted(() => ({
  loadData: vi.fn(),
}));

vi.mock("../vega/loader", () => ({
  vegaLoadData: mocks.loadData,
}));

vi.mock("../data-editor/glide-data-editor", async () => {
  const React = await import("react");
  return {
    default: (props: { data: EditorRow[] }) =>
      React.createElement(
        "pre",
        { "data-testid": "editor-data" },
        JSON.stringify(props.data),
      ),
  };
});

function renderPlugin(data: PluginData, value: Edits) {
  const props: IPluginProps<Edits, PluginData> = {
    host: document.createElement("div"),
    data,
    value,
    setValue: vi.fn(),
    functions: {},
  };
  return React.createElement(
    Suspense,
    { fallback: null },
    DataEditorPlugin.render(props),
  );
}

describe("DataEditorPlugin", () => {
  beforeEach(() => {
    mocks.loadData.mockReset();
  });

  it("normalizes an unrecognized field type", () => {
    const result = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [],
      fieldTypes: [["geom", ["bogus_type", "geometry"]]],
      editableColumns: "all",
    });

    expect(result.fieldTypes).toEqual([["geom", ["unknown", "geometry"]]]);
  });

  it("keeps the geometry field type", () => {
    const result = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [],
      fieldTypes: [["geom", ["geometry", "geometry"]]],
      editableColumns: "all",
    });

    expect(result.fieldTypes).toEqual([["geom", ["geometry", "geometry"]]]);
  });

  it("applies the latest edits when an async data load completes", async () => {
    let resolveLoad: ((data: EditorRow[]) => void) | undefined;
    mocks.loadData.mockImplementationOnce(
      () =>
        new Promise<EditorRow[]>((resolve) => {
          resolveLoad = resolve;
        }),
    );

    const data = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: "data.csv",
      fieldTypes: null,
      columnNames: ["name"],
      editableColumns: "all",
    });
    const result = render(renderPlugin(data, { edits: [] }));
    result.rerender(
      renderPlugin(data, {
        edits: [{ rowIdx: 0, columnId: "name", value: "latest" }],
      }),
    );
    expect(resolveLoad).toBeDefined();
    resolveLoad?.([{ name: "original" }]);

    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ name: "latest" }]),
      );
    });
  });

  it("applies edit updates after data has loaded", async () => {
    const data = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [{ name: "original" }],
      fieldTypes: null,
      columnNames: ["name"],
      editableColumns: "all",
    });
    const result = render(renderPlugin(data, { edits: [] }));
    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ name: "original" }]),
      );
    });

    result.rerender(
      renderPlugin(data, {
        edits: [{ rowIdx: 0, columnId: "name", value: "updated" }],
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ name: "updated" }]),
      );
    });
  });

  it("ignores a superseded async data load", async () => {
    let resolveFirst: ((data: EditorRow[]) => void) | undefined;
    let resolveSecond: ((data: EditorRow[]) => void) | undefined;
    mocks.loadData.mockImplementation((source: string) => {
      return new Promise<EditorRow[]>((resolve) => {
        if (source === "first.csv") {
          resolveFirst = resolve;
        } else {
          resolveSecond = resolve;
        }
      });
    });

    const makeData = (source: string) =>
      DataEditorPlugin.validator.parse({
        initialValue: { edits: [] },
        label: null,
        data: source,
        fieldTypes: null,
        columnNames: ["source"],
        editableColumns: "all",
      });
    const result = render(renderPlugin(makeData("first.csv"), { edits: [] }));
    result.rerender(renderPlugin(makeData("second.csv"), { edits: [] }));

    expect(resolveFirst).toBeDefined();
    expect(resolveSecond).toBeDefined();
    resolveSecond?.([{ source: "second" }]);
    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ source: "second" }]),
      );
    });

    await act(async () => {
      resolveFirst?.([{ source: "first" }]);
      await Promise.resolve();
    });
    expect(screen.getByTestId("editor-data")).toHaveTextContent(
      JSON.stringify([{ source: "second" }]),
    );
  });
});
