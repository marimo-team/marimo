/* Copyright 2024 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import {
  ToggleLeftIcon,
  CalendarIcon,
  HashIcon,
  TypeIcon,
  ListOrderedIcon,
  type LucideIcon,
} from "lucide-react";

/**
 * Maps a data type to an icon.
 */
export const DATA_TYPE_ICON: Record<DataType, LucideIcon> = {
  boolean: ToggleLeftIcon,
  date: CalendarIcon,
  number: HashIcon,
  string: TypeIcon,
  integer: ListOrderedIcon,
  unknown: TypeIcon,
};
