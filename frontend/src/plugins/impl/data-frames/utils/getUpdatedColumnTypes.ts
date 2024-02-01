/* Copyright 2024 Marimo. All rights reserved. */
import { logNever } from "@/utils/assertNever";
import { TransformType } from "../schema";
import { Objects } from "@/utils/objects";
import { ColumnDataTypes } from "../types";

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

  let next: ColumnDataTypes = { ...columnTypes };
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

      next[transform.column_id] = transform.data_type;
      return next;
    case "rename_column":
      if (!transform.new_column_id) {
        return next;
      }
      return Objects.fromEntries(
        Objects.entries(next).map(([k, v]) => {
          if (k === transform.column_id) {
            return [transform.new_column_id, v];
          }
          return [k, v];
        }),
      );
    case "group_by":
      return Objects.filter(
        next,
        (_v, k) => !transform.column_ids.includes(k as string),
      );
    case "aggregate":
      return Objects.filter(next, (_v, k) =>
        transform.column_ids.includes(k as string),
      );
    case "select_columns":
      return Objects.filter(next, (_v, k) =>
        transform.column_ids.includes(k as string),
      );
    case "filter_rows":
    case "shuffle_rows":
    case "sample_rows":
    case "sort_column":
      return next;
    default:
      logNever(transform);
      return next;
  }
}
