/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { DataEditorPlugin } from "../impl/DataEditorPlugin";
import { DataTablePlugin } from "../impl/DataTablePlugin";
import { DataFramePlugin } from "../impl/data-frames/DataFramePlugin";
import { PlotlyPlugin } from "../impl/plotly/PlotlyPlugin";
import { VegaPlugin } from "../impl/vega/VegaPlugin";

describe("plugin object schemas", () => {
  const rows = [{ value: 1, extra: { nested: true } }];
  const styles = { "0": { value: { color: "red", customProperty: 1 } } };
  const tableData = {
    initialValue: [],
    label: null,
    data: rows,
    totalRows: 1,
    totalColumns: 1,
    rowHeaders: [],
    cellStyles: styles,
  };

  it("preserves table rows and arbitrary cell style fields", () => {
    expect(DataTablePlugin.validator.parse(tableData)).toMatchObject({
      data: rows,
      cellStyles: styles,
      pageSize: 10,
    });
  });

  it("preserves data editor row fields", () => {
    expect(
      DataEditorPlugin.validator.parse({
        initialValue: { edits: [] },
        label: null,
        data: rows,
        editableColumns: "all",
      }),
    ).toMatchObject({ data: rows, columnNames: [] });
  });

  it("preserves table RPC payload fields", () => {
    const functions = DataTablePlugin.functions!;
    const searchResult = {
      data: rows,
      total_rows: 1,
      cell_styles: styles,
      cell_hover_texts: null,
    };
    expect(functions.search.output.parse(searchResult)).toEqual(searchResult);
    expect(functions.get_row_ids!.input.parse({ custom: true })).toEqual({
      custom: true,
    });
    expect(functions.get_data_url!.input.parse({ custom: true })).toEqual({
      custom: true,
    });
    expect(
      functions.get_data_url!.output.parse({ data_url: rows, format: "json" }),
    ).toEqual({ data_url: rows, format: "json" });
  });

  it("preserves dataframe search row fields", () => {
    const result = { data: rows, total_rows: 1 };
    expect(DataFramePlugin.functions!.search.output.parse(result)).toEqual(
      result,
    );
  });

  it("preserves Plotly figure and config fields", () => {
    const data = {
      figure: { data: [], layout: { title: "Chart" } },
      config: { responsive: true },
    };
    expect(new PlotlyPlugin().validator.parse(data)).toEqual(data);
  });

  it("preserves Vega spec and embed options fields and defaults", () => {
    const spec = { mark: "bar", encoding: { x: { field: "value" } } };
    const validator = new VegaPlugin().validator;
    expect(validator.parse({ spec })).toEqual({
      spec,
      chartSelection: true,
      fieldSelection: true,
      embedOptions: {},
    });
    expect(
      validator.parse({ spec, embedOptions: { actions: false } }).embedOptions,
    ).toEqual({ actions: false });
  });

  it("rejects scalar values where plugin objects are required", () => {
    expect(
      DataTablePlugin.validator.safeParse({ ...tableData, data: [42] }).success,
    ).toBe(false);
    expect(
      new PlotlyPlugin().validator.safeParse({ figure: 42, config: {} })
        .success,
    ).toBe(false);
    expect(
      new VegaPlugin().validator.safeParse({ spec: {}, embedOptions: 42 })
        .success,
    ).toBe(false);
  });
});
