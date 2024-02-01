/* Copyright 2024 Marimo. All rights reserved. */
import { TransformType } from "@/plugins/impl/data-frames/schema";
import { logNever } from "@/utils/assertNever";
import { OperatorType } from "../utils/operators";

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
      return `${dfName}["${column_id}"].astype("${data_type}", errors="${errors}")`;
    }
    case "rename_column": {
      const { column_id, new_column_id } = transform;
      return `${dfName}.rename(columns={"${column_id}": "${new_column_id}"})`;
    }
    case "sort_column": {
      const { column_id, ascending, na_position } = transform;
      const args = argsList(
        `by="${column_id}"`,
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
        .map((column_id) => `"${column_id}": ${listOfStrings(aggregations)}`)
        .join(", ")}})`;
    }
    case "group_by": {
      const { column_ids, aggregation, drop_na } = transform;
      const args = argsList(
        listOfStrings(column_ids),
        drop_na ? "dropna=True" : "",
      );
      return `${dfName}.groupby(${args}).${aggregation}()`;
    }
    case "select_columns": {
      const { column_ids } = transform;
      if (column_ids.length === 0) {
        return dfName;
      }
      if (column_ids.length === 1) {
        return `${dfName}["${column_ids[0]}"]`;
      }
      return `${dfName}[${listOfStrings(column_ids)}]`;
    }
    case "sample_rows": {
      const { n } = transform;
      return `${dfName}.sample(n=${n})`;
    }
    case "shuffle_rows":
      return `${dfName}.sample(frac=1)`;

    default:
      logNever(transform);
      return "";
  }
}

function generateWhereClause(
  dfName: string,
  where: {
    column_id: string;
    operator: OperatorType;
    value?: unknown;
  },
): string {
  const { column_id, operator, value } = where;
  switch (operator) {
    case "==":
      return `${dfName}["${column_id}"] == ${asString(value)}`;
    case "equals":
      return `${dfName}["${column_id}"].eq(${asString(value)})`;
    case "does_not_equal":
      return `${dfName}["${column_id}"].ne(${asString(value)})`;
    case "contains":
      return `${dfName}["${column_id}"].str.contains(${asString(value)})`;
    case "regex":
      return `${dfName}["${column_id}"].str.contains(${asString(
        value,
      )}, regex=True)`;
    case "starts_with":
      return `${dfName}["${column_id}"].str.startswith(${asString(value)})`;
    case "ends_with":
      return `${dfName}["${column_id}"].str.endswith(${asString(value)})`;
    case "in":
      return `${dfName}["${column_id}"].isin(${listOfStrings(value)})`;
    case "!=":
      return `${dfName}["${column_id}"].ne(${asString(value)})`;
    case ">":
      return `${dfName}["${column_id}"] > ${asString(value)}`;
    case ">=":
      return `${dfName}["${column_id}"] >= ${asString(value)}`;
    case "<":
      return `${dfName}["${column_id}"] < ${asString(value)}`;
    case "<=":
      return `${dfName}["${column_id}"] <= ${asString(value)}`;
    case "is_nan":
      return `${dfName}["${column_id}"].isna()`;
    case "is_not_nan":
      return `${dfName}["${column_id}"].notna()`;
    case "is_true":
      return `${dfName}["${column_id}"].eq(True)`;
    case "is_false":
      return `${dfName}["${column_id}"].eq(False)`;
    default:
      logNever(operator);
      return "df";
  }
}

function asString(value: unknown): string {
  if (typeof value === "string") {
    return `"${value}"`;
  }
  return `${value}`;
}

function listOfStrings(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(asString).join(", ")}]`;
  }
  return asString(value);
}

function argsList(...args: string[]): string {
  return args.filter(Boolean).join(", ");
}
