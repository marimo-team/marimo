/* Copyright 2023 Marimo. All rights reserved. */
import { TransformType } from "@/plugins/impl/data-frames/schema";
import { logNever } from "@/utils/assertNever";

export function pythonPrintTransforms(
  dfName: string,
  transforms: TransformType[]
): string {
  const dfNextName = `${dfName}_next`;
  const transformStrs = transforms.map(
    (transform, idx) => `${dfNextName} = ${pythonPrint(dfNextName, transform)}`
  );

  return [`${dfNextName} = ${dfName}.copy()`, ...transformStrs].join("\n");
}

export function pythonPrint(dfName: string, transform: TransformType): string {
  switch (transform.type) {
    case "column_conversion": {
      const { column_id, data_type } = transform;
      return `${dfName}["${column_id}"].astype("${data_type}")`;
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
        na_position === "last" ? "" : `na_position="${na_position}"`
      );
      return `${dfName}.sort_values(${args})`;
    }
    case "filter_rows": {
      const { operation, where } = transform;
      const whereClause = where
        .map((condition) =>
          `${dfName}["${condition.column_id}"] ${condition.operator} ${condition.value}`.trim()
        )
        .join(" and ");
      return operation === "keep_rows"
        ? `${dfName}[${whereClause}]`
        : `${dfName}[~${whereClause}]`;
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
        drop_na ? "dropna=True" : ""
      );
      return `${dfName}.groupby(${args}).${aggregation}()`;
    }

    default:
      logNever(transform);
      return "";
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
