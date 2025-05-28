/* Copyright 2024 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import {
  ToggleLeftIcon,
  CalendarIcon,
  HashIcon,
  TypeIcon,
  type LucideIcon,
  CalendarClockIcon,
  ClockIcon,
  CurlyBracesIcon,
} from "lucide-react";
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

export const DATA_TYPE_COLOR: Record<DataType | SelectableDataType, string> = {
  boolean: "bg-[var(--orange-5)]",
  date: "bg-[var(--grass-4)]",
  time: "bg-[var(--grass-4)]",
  datetime: "bg-[var(--grass-4)]",
  temporal: "bg-[var(--grass-4)]",
  number: "bg-[var(--purple-4)]",
  string: "bg-[var(--blue-4)]",
  integer: "bg-[var(--purple-4)]",
  unknown: "bg-[var(--slate-4)]",
};
