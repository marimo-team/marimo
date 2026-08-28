/* Copyright 2026 Marimo. All rights reserved. */

import React, { Suspense } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { z } from "zod";
import type { IPluginProps } from "../../types";
import type { Edits } from "../data-editor/types";
import { DataEditorPlugin } from "../DataEditorPlugin";

const mocks = vi.hoisted(() => ({
  loadData: vi.fn(),
}));

vi.mock("../vega/loader", () => ({
  vegaLoadData: mocks.loadData,
}));

vi.mock("../data-editor/glide-data-editor", async () => {
  const React = await import("react");
  return {
    default: (props: { data: Record<string, unknown>[] }) =>
      React.createElement(
        "pre",
        { "data-testid": "editor-data" },
        JSON.stringify(props.data),
      ),
  };
});

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
    let resolveLoad: ((data: Record<string, unknown>[]) => void) | undefined;
    mocks.loadData.mockImplementationOnce(
      () =>
        new Promise<Record<string, unknown>[]>((resolve) => {
          resolveLoad = resolve;
        }),
    );

    const plugin = DataEditorPlugin;
    const data = plugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: "data.csv",
      fieldTypes: null,
      columnNames: ["name"],
      editableColumns: "all",
    });
    const makeProps = (
      value: Edits,
    ): IPluginProps<Edits, z.infer<typeof DataEditorPlugin.validator>> => ({
      host: document.createElement("div"),
      data,
      value,
      setValue: vi.fn(),
      functions: {},
    });
    const renderPlugin = (value: Edits) =>
      React.createElement(
        Suspense,
        { fallback: null },
        plugin.render(makeProps(value)),
      );

    const result = render(renderPlugin({ edits: [] }));
    result.rerender(
      renderPlugin({
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
    const plugin = DataEditorPlugin;
    const data = plugin.validator.parse({
      initialValue: { edits: [] },
      label: null,
      data: [{ name: "original" }],
      fieldTypes: null,
      columnNames: ["name"],
      editableColumns: "all",
    });
    const makeProps = (
      value: Edits,
    ): IPluginProps<Edits, z.infer<typeof DataEditorPlugin.validator>> => ({
      host: document.createElement("div"),
      data,
      value,
      setValue: vi.fn(),
      functions: {},
    });
    const renderPlugin = (value: Edits) =>
      React.createElement(
        Suspense,
        { fallback: null },
        plugin.render(makeProps(value)),
      );

    const result = render(renderPlugin({ edits: [] }));
    await waitFor(() => {
      expect(screen.getByTestId("editor-data")).toHaveTextContent(
        JSON.stringify([{ name: "original" }]),
      );
    });

    result.rerender(
      renderPlugin({
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
    let resolveFirst: ((data: Record<string, unknown>[]) => void) | undefined;
    let resolveSecond: ((data: Record<string, unknown>[]) => void) | undefined;
    mocks.loadData.mockImplementation((source: string) => {
      return new Promise<Record<string, unknown>[]>((resolve) => {
        if (source === "first.csv") {
          resolveFirst = resolve;
        } else {
          resolveSecond = resolve;
        }
      });
    });

    const plugin = DataEditorPlugin;
    const makeData = (source: string) =>
      plugin.validator.parse({
        initialValue: { edits: [] },
        label: null,
        data: source,
        fieldTypes: null,
        columnNames: ["source"],
        editableColumns: "all",
      });
    const makeProps = (
      data: z.infer<typeof DataEditorPlugin.validator>,
    ): IPluginProps<Edits, z.infer<typeof DataEditorPlugin.validator>> => ({
      host: document.createElement("div"),
      data,
      value: { edits: [] },
      setValue: vi.fn(),
      functions: {},
    });
    const renderPlugin = (data: z.infer<typeof DataEditorPlugin.validator>) =>
      React.createElement(
        Suspense,
        { fallback: null },
        plugin.render(makeProps(data)),
      );

    const result = render(renderPlugin(makeData("first.csv")));
    result.rerender(renderPlugin(makeData("second.csv")));

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
