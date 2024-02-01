/* Copyright 2024 Marimo. All rights reserved. */
import { pythonPrint } from "@/plugins/impl/data-frames/python/python-print";
import { TransformType } from "@/plugins/impl/data-frames/schema";
import { expect, describe, it } from "vitest";
import {
  BOOLEAN_OPERATORS,
  DATE_OPERATORS,
  NUMERIC_OPERATORS,
  STRING_OPERATORS,
} from "../../utils/operators";
import { Objects } from "@/utils/objects";

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
      `"df["my_column"].astype("int8", errors="ignore")"`,
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
      `"df.rename(columns={"old_name": "new_name"})"`,
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
      `"df.sort_values(by="my_column", ascending=False, na_position="first")"`,
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
    expect(result).toMatchInlineSnapshot(`"df.agg({"my_column": ["mean"]})"`);

    const transform2: TransformType = {
      type: "aggregate",
      column_ids: [],
      aggregations: ["mean"],
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot(`"df.agg(["mean"])"`);

    const transform3: TransformType = {
      type: "aggregate",
      column_ids: ["my_column"],
      aggregations: ["mean", "sum"],
    };
    const result3 = pythonPrint("df", transform3);
    expect(result3).toMatchInlineSnapshot(
      `"df.agg({"my_column": ["mean", "sum"]})"`,
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
      `"df.groupby(["my_column"], dropna=True).sum()"`,
    );

    const transform2: TransformType = {
      type: "group_by",
      column_ids: ["my_column", "my_column2"],
      aggregation: "sum",
      drop_na: false,
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot(
      `"df.groupby(["my_column", "my_column2"]).sum()"`,
    );
  });
});

// Test for select_columns
it("generates correct Python code for select_columns", () => {
  const transform: TransformType = {
    type: "select_columns",
    column_ids: ["my_column"],
  };
  const result = pythonPrint("df", transform);
  expect(result).toMatchInlineSnapshot(`"df["my_column"]"`);

  const transform2: TransformType = {
    type: "select_columns",
    column_ids: ["my_column", "my_column2"],
  };
  const result2 = pythonPrint("df", transform2);
  expect(result2).toMatchInlineSnapshot(`"df[["my_column", "my_column2"]]"`);
});

// Test for sample_rows
it("generates correct Python code for sample_rows", () => {
  const transform: TransformType = {
    type: "sample_rows",
    n: 42,
    seed: 10,
    replace: false,
  };
  const result = pythonPrint("df", transform);
  expect(result).toMatchInlineSnapshot('"df.sample(n=42)"');
});

// Test for shuffle_rows
it("generates correct Python code for shuffle_rows", () => {
  const transform: TransformType = {
    type: "shuffle_rows",
    seed: 10,
  };
  const result = pythonPrint("df", transform);
  expect(result).toMatchInlineSnapshot('"df.sample(frac=1)"');
});

describe("pythonPrint: filter", () => {
  it("handles filter vs keep", () => {
    const result = pythonPrint("df", {
      type: "filter_rows",
      operation: "keep_rows",
      where: [
        {
          column_id: "my_column",
          operator: "==",
          value: 42,
        },
      ],
    });
    expect(result).toMatchInlineSnapshot(`"df[df["my_column"] == 42]"`);

    const result2 = pythonPrint("df", {
      type: "filter_rows",
      operation: "remove_rows",
      where: [
        {
          column_id: "my_column",
          operator: "==",
          value: 42,
        },
      ],
    });
    expect(result2).toMatchInlineSnapshot(`"df[~((df["my_column"] == 42))]"`);
  });

  it("handle multiple where clauses", () => {
    const result = pythonPrint("df", {
      type: "filter_rows",
      operation: "keep_rows",
      where: [
        {
          column_id: "my_column",
          operator: "==",
          value: 42,
        },
        {
          column_id: "my_column2",
          operator: "==",
          value: 43,
        },
      ],
    });
    expect(result).toMatchInlineSnapshot(
      `"df[(df["my_column"] == 42) & (df["my_column2"] == 43)]"`,
    );
  });

  // Test for filter_rows for strings
  it.each(Objects.entries(STRING_OPERATORS))(
    "filter_rows > string > %s",
    (operator) => {
      const transform: TransformType = {
        type: "filter_rows",
        operation: "keep_rows",
        where: [
          {
            column_id: "my_column",
            operator: operator,
            value: "val",
          },
        ],
      };
      const result = pythonPrint("df", transform);
      expect(result).toMatchSnapshot();
    },
  );

  // Test for filter_rows for booleans
  it.each(Objects.entries(BOOLEAN_OPERATORS))(
    "filter_rows > date > %s",
    (operator) => {
      const transform: TransformType = {
        type: "filter_rows",
        operation: "keep_rows",
        where: [
          {
            column_id: "my_column",
            operator: operator,
            value: true,
          },
        ],
      };
      const result = pythonPrint("df", transform);
      expect(result).toMatchSnapshot();
    },
  );

  // Test for filter_rows for dates
  it.each(Objects.entries(DATE_OPERATORS))(
    "filter_rows > date > %s",
    (operator) => {
      const transform: TransformType = {
        type: "filter_rows",
        operation: "keep_rows",
        where: [
          {
            column_id: "my_column",
            operator: operator,
            value: 1000,
          },
        ],
      };
      const result = pythonPrint("df", transform);
      expect(result).toMatchSnapshot();
    },
  );

  // Test for filter_rows for numbers
  it.each(Objects.entries(NUMERIC_OPERATORS))(
    "filter_rows > number > %s",
    (operator) => {
      const transform: TransformType = {
        type: "filter_rows",
        operation: "keep_rows",
        where: [
          {
            column_id: "my_column",
            operator: operator,
            value: 42,
          },
        ],
      };
      const result = pythonPrint("df", transform);
      expect(result).toMatchSnapshot();
    },
  );
});
