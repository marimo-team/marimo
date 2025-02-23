/* Copyright 2024 Marimo. All rights reserved. */
import type { TransformType } from "@/plugins/impl/data-frames/schema";
import { logNever } from "@/utils/assertNever";
import type { OperatorType } from "../utils/operators";
import type { ColumnId } from "../types";

export function pythonPrintTransforms(
  dfName: string,
  transforms: TransformType[],
): string {
  const dfNextName = `${dfName}_next`;
  const transformStrs = transforms.map(
    (transform) => `${dfNextName} = ${pythonPrint(dfNextName, transform)}`,
  );

  return [`${dfNextName} = ${dfName}`, ...transformStrs].join("\n");
}

export function pythonPrint(dfName: string, transform: TransformType): string {
  switch (transform.type) {
    case "column_conversion": {
      const { column_id, data_type, errors } = transform;
      return `${dfName}[${asLiteral(
        column_id,
      )}].astype("${data_type}", errors="${errors}")`;
    }
    case "rename_column": {
      const { column_id, new_column_id } = transform;
      return `${dfName}.rename(columns={${asLiteral(column_id)}: ${asLiteral(
        new_column_id,
      )}})`;
    }
    case "sort_column": {
      const { column_id, ascending, na_position } = transform;
      const args = argsList(
        `by=${asLiteral(column_id)}`,
        ascending ? "" : "ascending=False",
        na_position === "last" ? "" : `na_position="${na_position}"`,
      );
      return `${dfName}.sort_values(${args})`;
    }
    case "filter_rows": {
      const { operation, where } = transform;
      if (where.length === 0) {
        return dfName;
      }

      const whereClauses = where.map((condition) =>
        generateWhereClause(dfName, condition),
      );
      if (operation === "keep_rows" && whereClauses.length === 1) {
        return `${dfName}[${whereClauses[0]}]`;
      }

      const expression = whereClauses
        .map((clause) => `(${clause})`)
        .join(" & ");

      return operation === "keep_rows"
        ? `${dfName}[${expression}]`
        : `${dfName}[~(${expression})]`;
    }
    case "aggregate": {
      const { column_ids, aggregations } = transform;
      if (column_ids.length === 0) {
        return `${dfName}.agg(${listOfStrings(aggregations)})`;
      }
      return `${dfName}.agg({${column_ids
        .map(
          (columnId) =>
            `${asLiteral(columnId)}: ${listOfStrings(aggregations)}`,
        )
        .join(", ")}})`;
    }
    case "group_by": {
      const { column_ids, aggregation, drop_na } = transform;
      const args = argsList(
        listOfStrings(column_ids),
        drop_na ? "dropna=True" : "",
      );
      let aggArgs = "";
      if (aggregation === "mean") {
        aggArgs = "numeric_only=True";
      } else if (aggregation === "median") {
        aggArgs = "numeric_only=True";
      }
      return `${dfName}.groupby(${args}).${aggregation}(${aggArgs})`;
    }
    case "select_columns": {
      const { column_ids } = transform;
      if (column_ids.length === 0) {
        return dfName;
      }
      if (column_ids.length === 1) {
        return `${dfName}[${asLiteral(column_ids[0])}]`;
      }
      return `${dfName}[${listOfStrings(column_ids)}]`;
    }
    case "sample_rows": {
      const { n } = transform;
      return `${dfName}.sample(n=${n})`;
    }
    case "shuffle_rows":
      return `${dfName}.sample(frac=1)`;
    case "explode_columns": {
      const { column_ids } = transform;
      return `${dfName}.explode(${listOfStrings(column_ids)})`;
    }
    case "expand_dict": {
      const columnId = asLiteral(transform.column_id);
      const args = `df.pop(${columnId}).values.tolist())`;
      return `${dfName}.join(pd.DataFrame(${args})`;
    }
    case "unique": {
      const { column_ids, keep } = transform;
      const keepArg = keep === "none" ? "False" : keep;
      return `${dfName}.drop_duplicates(subset=${listOfStrings(
        column_ids,
      )}, keep=${keepArg})`;
    }
    default:
      logNever(transform);
      return "";
  }
}

function generateWhereClause(
  dfName: string,
  where: {
    column_id: ColumnId;
    operator: OperatorType;
    value?: unknown;
  },
): string {
  const { column_id, operator, value } = where;
  switch (operator) {
    case "==":
      return `${dfName}[${asLiteral(column_id)}] == ${asLiteral(value)}`;
    case "equals":
      return `${dfName}[${asLiteral(column_id)}].eq(${asLiteral(value)})`;
    case "does_not_equal":
      return `${dfName}[${asLiteral(column_id)}].ne(${asLiteral(value)})`;
    case "contains":
      return `${dfName}[${asLiteral(column_id)}].str.contains(${asLiteral(
        value,
      )})`;
    case "regex":
      return `${dfName}[${asLiteral(column_id)}].str.contains(${asLiteral(
        value,
      )}, regex=True)`;
    case "starts_with":
      return `${dfName}[${asLiteral(column_id)}].str.startswith(${asLiteral(
        value,
      )})`;
    case "ends_with":
      return `${dfName}[${asLiteral(column_id)}].str.endswith(${asLiteral(
        value,
      )})`;
    case "in":
      return `${dfName}[${asLiteral(column_id)}].isin(${listOfStrings(value)})`;
    case "!=":
      return `${dfName}[${asLiteral(column_id)}].ne(${asLiteral(value)})`;
    case ">":
      return `${dfName}[${asLiteral(column_id)}] > ${asLiteral(value)}`;
    case ">=":
      return `${dfName}[${asLiteral(column_id)}] >= ${asLiteral(value)}`;
    case "<":
      return `${dfName}[${asLiteral(column_id)}] < ${asLiteral(value)}`;
    case "<=":
      return `${dfName}[${asLiteral(column_id)}] <= ${asLiteral(value)}`;
    case "is_nan":
      return `${dfName}[${asLiteral(column_id)}].isna()`;
    case "is_not_nan":
      return `${dfName}[${asLiteral(column_id)}].notna()`;
    case "is_true":
      return `${dfName}[${asLiteral(column_id)}].eq(True)`;
    case "is_false":
      return `${dfName}[${asLiteral(column_id)}].eq(False)`;
    default:
      logNever(operator);
      return "df";
  }
}

function asLiteral(value: unknown): string {
  if (typeof value === "string") {
    return `"${value}"`;
  }
  return `${value}`;
}

function listOfStrings(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(asLiteral).join(", ")}]`;
  }
  return asLiteral(value);
}

function argsList(...args: string[]): string {
  return args.filter(Boolean).join(", ");
}
