/* Copyright 2026 Marimo. All rights reserved. */

import {
  CalendarClockIcon,
  CalendarIcon,
  ClockIcon,
  CurlyBracesIcon,
  HashIcon,
  type LucideIcon,
  ToggleLeftIcon,
  TypeIcon,
} from "lucide-react";
import type { DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import type { SelectableDataType } from "../data-table/charts/types";

/**
 * Maps a data type to an icon.
 */
export const DATA_TYPE_ICON: Record<DataType | SelectableDataType, LucideIcon> =
  {
    boolean: ToggleLeftIcon,
    date: CalendarIcon,
    time: ClockIcon,
    datetime: CalendarClockIcon,
    temporal: CalendarClockIcon,
    number: HashIcon,
    string: TypeIcon,
    integer: HashIcon,
    unknown: CurlyBracesIcon,
  };

/**
 * A newer backend can send a data type this frontend does not know. Resolve
 * those to `unknown` before indexing icon or color maps.
 */
export function resolveDataType(
  dataType: DataType | SelectableDataType,
): DataType | SelectableDataType {
  return Object.hasOwn(DATA_TYPE_ICON, dataType) ? dataType : "unknown";
}

export function getDataTypeColor(
  dataType: DataType | SelectableDataType,
): string {
  switch (dataType) {
    case "boolean":
      return "bg-(--orange-4)";
    case "date":
    case "time":
    case "datetime":
    case "temporal":
      return "bg-(--grass-4) dark:bg-(--grass-5)";
    case "number":
    case "integer":
      return "bg-(--purple-4)";
    case "string":
      return "bg-(--blue-4)";
    case "unknown":
      return "bg-(--slate-4) dark:bg-(--slate-6)";
    default:
      logNever(dataType);
      return "bg-(--slate-4) dark:bg-(--slate-6)";
  }
}
