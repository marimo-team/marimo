/* Copyright 2026 Marimo. All rights reserved. */

import React, { Suspense } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import type { IPluginProps, Setter } from "../../types";
import type { GlideDataEditor } from "../data-editor/glide-data-editor";
import type { ColumnType, EditorRow, Edits } from "../data-editor/types";
import { DataEditorPlugin } from "../DataEditorPlugin";

type PluginData = z.infer<typeof DataEditorPlugin.validator>;

const mocks = vi.hoisted(() => ({
  loadData: vi.fn(),
  renderEditor:
    vi.fn<(props: React.ComponentProps<typeof GlideDataEditor>) => void>(),
}));

vi.mock("../vega/loader", () => ({
  vegaLoadData: mocks.loadData,
}));

vi.mock("../data-editor/glide-data-editor", async () => {
  const React = await import("react");
  return {
    default: (props: React.ComponentProps<typeof GlideDataEditor>) => {
      mocks.renderEditor(props);
      return React.createElement(
        React.Fragment,
        null,
        React.createElement(
          "pre",
          { "data-testid": "editor-data" },
          JSON.stringify(props.data),
        ),
        React.createElement(
          "pre",
          { "data-testid": "editor-fields" },
          JSON.stringify([...props.columnFields]),
        ),
      );
    },
  };
});

function renderPlugin(
  data: PluginData,
  value: Edits,
  setValue: Setter<Edits> = vi.fn(),
) {
  const props: IPluginProps<Edits, PluginData> = {
    host: document.createElement("div"),
    data,
    value,
    setValue,
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
    mocks.renderEditor.mockClear();
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

  it("parses dropdown column types", () => {
    const result = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [],
      fieldTypes: null,
      editableColumns: "all",
      columnTypes: { status: ["open", "closed"] },
    });

    expect(result.columnTypes).toEqual({ status: ["open", "closed"] });
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

  it("normalizes explicitly configured boolean columns", async () => {
    const data = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [{ active: "No" }, { active: "YES" }],
      fieldTypes: null,
      columnNames: ["active"],
      columnTypes: { active: "boolean" },
      editableColumns: "all",
    });
    render(renderPlugin(data, { edits: [] }));

    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ active: false }, { active: true }]),
      );
    });
  });

  it("keeps numeric-looking dropdown values as option strings", async () => {
    // Vega's CSV auto-parse turns "1" into 1 when no field types are sent.
    mocks.loadData.mockResolvedValueOnce([{ level: 1 }, { level: 2 }]);
    const data = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: "data.csv",
      fieldTypes: null,
      columnNames: ["level"],
      columnTypes: { level: ["1", "2", "3"] },
      editableColumns: "all",
    });
    render(renderPlugin(data, { edits: [] }));

    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ level: "1" }, { level: "2" }]),
      );
    });
  });

  it("treats dropdown columns as strings over a numeric field type", async () => {
    mocks.loadData.mockResolvedValueOnce([]);
    const data = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: "data.csv",
      fieldTypes: [["status", ["integer", "int64"]]],
      columnNames: ["status"],
      columnTypes: { status: ["open", "closed"] },
      editableColumns: "all",
    });
    render(renderPlugin(data, { edits: [] }));

    await waitFor(() => {
      expect(screen.getByTestId("editor-fields").textContent).toContain(
        '"string"',
      );
    });
    expect(screen.getByTestId("editor-fields").textContent).not.toContain(
      '"integer"',
    );
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

    mocks.renderEditor.mockClear();
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
    expect(mocks.renderEditor).toHaveBeenCalled();
    for (const [props] of mocks.renderEditor.mock.calls) {
      expect(props.data).toEqual([{ name: "updated" }]);
    }
  });

  it("accumulates cell edits through the plugin value", async () => {
    const data = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [{ name: "original" }],
      editableColumns: "all",
    });
    const Editor = () => {
      const [value, setValue] = React.useState<Edits>({ edits: [] });
      return renderPlugin(data, value, setValue);
    };
    render(React.createElement(Editor));
    await screen.findByTestId("editor-data");

    act(() => {
      const onAddEdits = mocks.renderEditor.mock.lastCall?.[0].onAddEdits;
      onAddEdits?.([{ rowIdx: 0, columnId: "name", value: "updated" }]);
      onAddEdits?.([{ rowIdx: 1, columnId: "name", value: "appended" }]);
    });

    expect(screen.getByTestId("editor-data").textContent).toBe(
      JSON.stringify([{ name: "updated" }, { name: "appended" }]),
    );
  });

  it("removes the previous editor while loading a replacement schema", async () => {
    const original = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [{ name: "original", day: "2026-11-06" }],
      editableColumns: "all",
    });
    const result = render(renderPlugin(original, { edits: [] }));
    await screen.findByTestId("editor-data");
    mocks.renderEditor.mockClear();

    let resolveLoad: ((data: EditorRow[]) => void) | undefined;
    mocks.loadData.mockImplementationOnce(
      () =>
        new Promise<EditorRow[]>((resolve) => {
          resolveLoad = resolve;
        }),
    );
    const replacement = DataEditorPlugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: "replacement.csv",
      columnNames: ["task", "done", "priority"],
      columnTypes: { done: "boolean", priority: ["01", "02", "10"] },
      editableColumns: ["task"],
    });
    result.rerender(
      renderPlugin(replacement, {
        edits: [{ rowIdx: 0, columnId: "task", value: "latest" }],
      }),
    );

    expect(screen.queryByTestId("editor-data")).toBeNull();
    expect(mocks.renderEditor).not.toHaveBeenCalled();
    await act(async () => {
      resolveLoad?.([{ task: "Review", done: "yes", priority: "01" }]);
    });
    await screen.findByTestId("editor-data");
    expect(mocks.renderEditor).toHaveBeenLastCalledWith(
      expect.objectContaining({
        data: [{ task: "latest", done: true, priority: "01" }],
        columnFields: new Map([
          ["task", "string"],
          ["done", "boolean"],
          ["priority", "string"],
        ]),
        columnTypes: new Map<string, ColumnType>([
          ["done", "boolean"],
          ["priority", ["01", "02", "10"]],
        ]),
        editableColumns: ["task"],
      }),
    );
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
