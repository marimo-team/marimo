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
import type { ScaleType } from "../data-table/chart-transforms/chart-schemas";

/**
 * Maps a data type to an icon.
 */
export const DATA_TYPE_ICON: Record<DataType | ScaleType, LucideIcon> = {
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
