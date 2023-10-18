/* Copyright 2023 Marimo. All rights reserved. */
import { pythonPrint } from "@/plugins/impl/data-frames/python/python-print";
import { TransformType } from "@/plugins/impl/data-frames/schema";
import { expect, describe, it } from "vitest";

describe("pythonPrint", () => {
  // Test for column_conversion
  it("generates correct Python code for column_conversion", () => {
    const transform: TransformType = {
      type: "column_conversion",
      column_id: "my_column",
      data_type: "int8",
      errors: "ignore",
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      '"df[\\"my_column\\"].astype(\\"int8\\")"'
    );
  });

  // Test for rename_column
  it("generates correct Python code for rename_column", () => {
    const transform: TransformType = {
      type: "rename_column",
      column_id: "old_name",
      new_column_id: "new_name",
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      '"df.rename(columns={\\"old_name\\": \\"new_name\\"})"'
    );
  });

  // Test for sort_column
  it("generates correct Python code for sort_column", () => {
    const transform: TransformType = {
      type: "sort_column",
      column_id: "my_column",
      ascending: false,
      na_position: "first",
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      '"df.sort_values(by=\\"my_column\\", ascending=False, na_position=\\"first\\")"'
    );
  });

  // Test for filter_rows
  it("generates correct Python code for filter_rows", () => {
    const transform: TransformType = {
      type: "filter_rows",
      operation: "keep_rows",
      where: [
        {
          column_id: "my_column",
          operator: ">",
          value: 10,
        },
      ],
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot('"df[df[\\"my_column\\"] > 10]"');

    const transform2: TransformType = {
      type: "filter_rows",
      operation: "remove_rows",
      where: [
        {
          column_id: "my_column",
          operator: ">",
          value: 10,
        },
        {
          column_id: "my_column2",
          operator: "==",
          value: "hello",
        },
      ],
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot(
      '"df[~df[\\"my_column\\"] > 10 and df[\\"my_column2\\"] == hello]"'
    );
  });

  // Test for aggregate
  it("generates correct Python code for aggregate", () => {
    const transform: TransformType = {
      type: "aggregate",
      column_ids: ["my_column"],
      aggregations: ["mean"],
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      '"df.agg({\\"my_column\\": [\\"mean\\"]})"'
    );

    const transform2: TransformType = {
      type: "aggregate",
      column_ids: [],
      aggregations: ["mean"],
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot('"df.agg([\\"mean\\"])"');

    const transform3: TransformType = {
      type: "aggregate",
      column_ids: ["my_column"],
      aggregations: ["mean", "sum"],
    };
    const result3 = pythonPrint("df", transform3);
    expect(result3).toMatchInlineSnapshot(
      '"df.agg({\\"my_column\\": [\\"mean\\", \\"sum\\"]})"'
    );
  });

  // Test for group_by
  it("generates correct Python code for group_by", () => {
    const transform: TransformType = {
      type: "group_by",
      column_ids: ["my_column"],
      aggregation: "sum",
      drop_na: true,
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      '"df.groupby([\\"my_column\\"], dropna=True).sum()"'
    );

    const transform2: TransformType = {
      type: "group_by",
      column_ids: ["my_column", "my_column2"],
      aggregation: "sum",
      drop_na: false,
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot(
      '"df.groupby([\\"my_column\\", \\"my_column2\\"]).sum()"'
    );
  });
});
