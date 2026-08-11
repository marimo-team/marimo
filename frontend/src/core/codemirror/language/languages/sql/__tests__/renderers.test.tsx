/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type {
  DataTable,
  DataTableColumn,
  DataType,
} from "@/core/kernel/messages";
import { renderColumnInfo, renderTableInfo } from "../renderers";

const geometryColumn = {
  name: "geom",
  type: "geometry" as DataType,
  external_type: "geometry",
  sample_values: [],
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
      columns: [geometryColumn],
      primary_keys: [],
      indexes: [],
    };

    const result = render(renderTableInfo(table));

    expect(result.container.querySelector("svg")).not.toBeNull();
  });

  it("renders column information with an unrecognized column type", () => {
    const result = render(renderColumnInfo(geometryColumn));

    expect(result.container.querySelector("svg")).not.toBeNull();
  });
});
