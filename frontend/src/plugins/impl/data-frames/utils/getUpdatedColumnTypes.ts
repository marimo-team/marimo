/* Copyright 2024 Marimo. All rights reserved. */
import { logNever } from "@/utils/assertNever";
import { Maps } from "@/utils/maps";
import type { TransformType } from "../schema";
import type { ColumnDataTypes, ColumnId } from "../types";
import { get } from "node:http";

/**
 * Given a list of transforms, return the updated column names/types.
 */
export function getUpdatedColumnTypes(
  transforms: TransformType[],
  columnTypes: ColumnDataTypes,
  uniqueColumnValues: Record<string, unknown[]>,
): ColumnDataTypes {
  if (!transforms || transforms.length === 0) {
    return columnTypes;
  }

  let next: ColumnDataTypes = new Map(columnTypes);
  for (const transform of transforms) {
    next = handleTransform(transform, next, uniqueColumnValues);
  }

  return next;
}

function cartesianProduct<T>(arrays: T[][]): T[][] {
  return arrays.reduce<T[][]>(
    (acc, curr) =>
      acc.flatMap(a => curr.map(c => [...a, c])),
    [[]]
  );
}

function handleTransform(
  transform: TransformType,
  next: ColumnDataTypes,
  uniqueColumnValues: Record<string, unknown[]>,
): ColumnDataTypes {
  switch (transform.type) {
    case "column_conversion":
      if (!transform.column_id) {
        return next;
      }

      next.set(transform.column_id, transform.data_type);
      return next;
    case "rename_column": {
      if (!transform.new_column_id) {
        return next;
      }
      const type = next.get(transform.column_id);
      if (type) {
        next.set(transform.new_column_id, type);
        next.delete(transform.column_id);
      }
      return next;
    }
    case "group_by": {
      const groupColumns = new Set(transform.column_ids ?? []);
      const aggregationColumns =
        transform.aggregation_column_ids &&
        transform.aggregation_column_ids.length > 0
          ? new Set(transform.aggregation_column_ids)
          : null;

      const updated = new Map<ColumnId, string>();

      for (const [columnId, type] of next.entries()) {
        if (groupColumns.has(columnId)) {
          updated.set(columnId, type);
          continue;
        }

        if (aggregationColumns === null || aggregationColumns.has(columnId)) {
          updated.set(`${columnId}_${transform.aggregation}` as ColumnId, type);
        }
      }

      return updated;
    }
    case "pivot":{
      const updated = new Map<ColumnId, string>();

      for (const [columnId, type] of next.entries()) {
        if (transform.index_column_ids.includes(columnId)) {
          updated.set(columnId, type);
        }
      }

      const uniqueValues = transform.column_ids.map((columnId) => {
        const values = uniqueColumnValues[columnId.toString()] || [];
        return values;
      })

      const rawColumns = cartesianProduct([transform.value_column_ids, ...uniqueValues]);
      for (const rawColumn of rawColumns) {
        const newColumn = `${(rawColumn as string[]).join("_")}_${transform.aggregation}`;
        const type = transform.aggregation === "len" ? "int64" : next.get(rawColumn[0] as ColumnId);
        updated.set(newColumn as ColumnId, type as string);
      }

      return updated;
    }
    case "aggregate":
      return Maps.filterMap(next, (_v, k) => transform.column_ids.includes(k));
    case "select_columns":
      return Maps.filterMap(next, (_v, k) => transform.column_ids.includes(k));
    case "filter_rows":
    case "shuffle_rows":
    case "sample_rows":
    case "sort_column":
    case "expand_dict":
    case "explode_columns":
    case "unique":
      return next;
    default:
      logNever(transform);
      return next;
  }
}
