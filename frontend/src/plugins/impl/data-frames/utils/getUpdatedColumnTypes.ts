/* Copyright 2024 Marimo. All rights reserved. */
import { logNever } from "@/utils/assertNever";
import type { TransformType } from "../schema";
import type { ColumnDataTypes } from "../types";
import { Maps } from "@/utils/maps";

/**
 * Given a list of transforms, return the updated column names/types.
 */
export function getUpdatedColumnTypes(
  transforms: TransformType[],
  columnTypes: ColumnDataTypes,
): ColumnDataTypes {
  if (!transforms || transforms.length === 0) {
    return columnTypes;
  }

  let next: ColumnDataTypes = new Map(columnTypes);
  for (const transform of transforms) {
    next = handleTransform(transform, next);
  }

  return next;
}

function handleTransform(
  transform: TransformType,
  next: ColumnDataTypes,
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
    case "group_by":
      return Maps.filterMap(next, (_v, k) => !transform.column_ids.includes(k));
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
