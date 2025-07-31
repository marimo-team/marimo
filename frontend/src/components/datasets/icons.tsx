/* Copyright 2024 Marimo. All rights reserved. */

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

export function getDataTypeColor(
  dataType: DataType | SelectableDataType,
): string {
  switch (dataType) {
    case "boolean":
      return "bg-[var(--orange-4)]";
    case "date":
    case "time":
    case "datetime":
    case "temporal":
      return "bg-[var(--grass-4)] dark:bg-[var(--grass-5)]";
    case "number":
    case "integer":
      return "bg-[var(--purple-4)]";
    case "string":
      return "bg-[var(--blue-4)]";
    case "unknown":
      return "bg-[var(--slate-4)] dark:bg-[var(--slate-6)]";
    default:
      logNever(dataType);
      return "bg-[var(--slate-4)] dark:bg-[var(--slate-6)]";
  }
}
