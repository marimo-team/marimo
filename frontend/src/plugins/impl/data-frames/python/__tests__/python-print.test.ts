/* Copyright 2024 Marimo. All rights reserved. */
import { pythonPrint } from "@/plugins/impl/data-frames/python/python-print";
import type { TransformType } from "@/plugins/impl/data-frames/schema";
import { expect, describe, it } from "vitest";
import {
  BOOLEAN_OPERATORS,
  DATE_OPERATORS,
  NUMERIC_OPERATORS,
  STRING_OPERATORS,
} from "../../utils/operators";
import { Objects } from "@/utils/objects";
import type { ColumnId } from "../../types";

describe("pythonPrint", () => {
  // Test for column_conversion
  it("generates correct Python code for column_conversion", () => {
    const transform: TransformType = {
      type: "column_conversion",
      column_id: "my_column" as ColumnId,
      data_type: "int8",
      errors: "ignore",
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      `"df["my_column"].astype("int8", errors="ignore")"`,
    );
  });

  it("generates correct Python code for column_conversion, for numeric columns", () => {
    const transform: TransformType = {
      type: "column_conversion",
      column_id: 1 as ColumnId,
      data_type: "int8",
      errors: "ignore",
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      `"df[1].astype("int8", errors="ignore")"`,
    );
  });

  // Test for rename_column
  it("generates correct Python code for rename_column", () => {
    const transform: TransformType = {
      type: "rename_column",
      column_id: "old_name" as ColumnId,
      new_column_id: "new_name" as ColumnId,
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      `"df.rename(columns={"old_name": "new_name"})"`,
    );
  });

  it("generates correct Python code for rename_column, for numeric columns", () => {
    const transform: TransformType = {
      type: "rename_column",
      column_id: 1 as ColumnId,
      new_column_id: 2 as ColumnId,
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(`"df.rename(columns={1: 2})"`);
  });

  // Test for sort_column
  it("generates correct Python code for sort_column", () => {
    const transform: TransformType = {
      type: "sort_column",
      column_id: "my_column" as ColumnId,
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
      column_ids: ["my_column"] as ColumnId[],
      aggregations: ["mean"],
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(`"df.agg({"my_column": ["mean"]})"`);

    const transform2: TransformType = {
      type: "aggregate",
      column_ids: [] as ColumnId[],
      aggregations: ["mean"],
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot(`"df.agg(["mean"])"`);

    const transform3: TransformType = {
      type: "aggregate",
      column_ids: [2] as ColumnId[],
      aggregations: ["mean", "sum"],
    };
    const result3 = pythonPrint("df", transform3);
    expect(result3).toMatchInlineSnapshot(`"df.agg({2: ["mean", "sum"]})"`);
  });

  // Test for group_by
  it("generates correct Python code for group_by", () => {
    const transform: TransformType = {
      type: "group_by",
      column_ids: ["my_column"] as ColumnId[],
      aggregation: "sum",
      drop_na: true,
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      `"df.groupby(["my_column"], dropna=True).sum()"`,
    );

    const transform2: TransformType = {
      type: "group_by",
      column_ids: ["my_column", "my_column2", 3] as ColumnId[],
      aggregation: "sum",
      drop_na: false,
    };
    const result2 = pythonPrint("df", transform2);
    expect(result2).toMatchInlineSnapshot(
      `"df.groupby(["my_column", "my_column2", 3]).sum()"`,
    );

    const transform3: TransformType = {
      type: "group_by",
      column_ids: ["my_column"] as ColumnId[],
      aggregation: "mean",
      drop_na: false,
    };
    const result3 = pythonPrint("df", transform3);
    expect(result3).toMatchInlineSnapshot(
      `"df.groupby(["my_column"]).mean(numeric_only=True)"`,
    );

    const transform4: TransformType = {
      type: "group_by",
      column_ids: ["my_column"] as ColumnId[],
      aggregation: "median",
      drop_na: false,
    };
    const result4 = pythonPrint("df", transform4);
    expect(result4).toMatchInlineSnapshot(
      `"df.groupby(["my_column"]).median(numeric_only=True)"`,
    );
  });
});

// Test for select_columns
it("generates correct Python code for select_columns", () => {
  const transform: TransformType = {
    type: "select_columns",
    column_ids: ["my_column"] as ColumnId[],
  };
  const result = pythonPrint("df", transform);
  expect(result).toMatchInlineSnapshot(`"df["my_column"]"`);

  const transform2: TransformType = {
    type: "select_columns",
    column_ids: ["my_column", "my_column2", 3] as ColumnId[],
  };
  const result2 = pythonPrint("df", transform2);
  expect(result2).toMatchInlineSnapshot(`"df[["my_column", "my_column2", 3]]"`);
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
          column_id: "my_column" as ColumnId,
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
          column_id: "my_column" as ColumnId,
          operator: "==",
          value: 42,
        },
      ],
    });
    expect(result2).toMatchInlineSnapshot(`"df[~((df["my_column"] == 42))]"`);
  });

  it("handle where clauses with numeric columns", () => {
    const result = pythonPrint("df", {
      type: "filter_rows",
      operation: "keep_rows",
      where: [
        {
          column_id: 2 as ColumnId,
          operator: "==",
          value: 43,
        },
      ],
    });
    expect(result).toMatchInlineSnapshot(`"df[df[2] == 43]"`);
  });

  it("handle multiple where clauses", () => {
    const result = pythonPrint("df", {
      type: "filter_rows",
      operation: "keep_rows",
      where: [
        {
          column_id: "my_column" as ColumnId,
          operator: "==",
          value: 42,
        },
        {
          column_id: 2 as ColumnId,
          operator: "==",
          value: 43,
        },
      ],
    });
    expect(result).toMatchInlineSnapshot(
      `"df[(df["my_column"] == 42) & (df[2] == 43)]"`,
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
            column_id: "my_column" as ColumnId,
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
            column_id: "my_column" as ColumnId,
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
            column_id: "my_column" as ColumnId,
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
            column_id: "my_column" as ColumnId,
            operator: operator,
            value: 42,
          },
        ],
      };
      const result = pythonPrint("df", transform);
      expect(result).toMatchSnapshot();
    },
  );

  // Test for explode_column
  it("generates correct Python code for explode_column", () => {
    const transform: TransformType = {
      type: "explode_columns",
      column_ids: ["my_column"] as ColumnId[],
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(`"df.explode(["my_column"])"`);
  });

  // Test for expand_dict
  it("generates correct Python code for expand_dict", () => {
    const transform: TransformType = {
      type: "expand_dict",
      column_id: "my_column" as ColumnId,
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      `"df.join(pd.DataFrame(df.pop("my_column").values.tolist()))"`,
    );
  });

  // Test for unique
  it("generates correct Python code for unique", () => {
    const transform: TransformType = {
      type: "unique",
      column_ids: ["my_column"] as ColumnId[],
      keep: "first",
    };
    const result = pythonPrint("df", transform);
    expect(result).toMatchInlineSnapshot(
      `"df.drop_duplicates(subset=["my_column"], keep="first")"`,
    );
  });
});
