/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type {
  DataTable,
  DataTableColumn,
  DataType,
} from "@/core/kernel/messages";
import { renderColumnInfo, renderTableInfo } from "../renderers";

const bogusColumn = {
  name: "geom",
  type: "bogus_type" as DataType,
  external_type: "geometry",
  sample_values: [],
} as DataTableColumn;

const geometryColumn = {
  ...bogusColumn,
  type: "geometry" as DataType,
} as DataTableColumn;

describe("SQL renderers", () => {
  it("renders table information with an unrecognized column type", () => {
    const table: DataTable = {
      name: "shapes",
      type: "table",
      source: "local",
      source_type: "local",
      num_rows: null,
      num_columns: 1,
      variable_name: null,
      columns: [bogusColumn],
      primary_keys: [],
      indexes: [],
    };

    const result = render(renderTableInfo(table));

    expect(result.container.querySelector("svg")).not.toBeNull();
  });

  it("renders column information with an unrecognized column type", () => {
    const result = render(renderColumnInfo(bogusColumn));

    expect(result.container.querySelector("svg")).not.toBeNull();
  });

  it("renders geometry column information with the map pin icon", () => {
    const result = render(renderColumnInfo(geometryColumn));

    expect(result.container.querySelector(".lucide-map-pin")).not.toBeNull();
  });
});
