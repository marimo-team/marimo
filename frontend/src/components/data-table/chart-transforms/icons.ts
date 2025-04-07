/* Copyright 2024 Marimo. All rights reserved. */

import {
  LineChartIcon,
  BarChartIcon,
  PieChartIcon,
  SigmaIcon,
  CircleSlash2,
  MinusIcon,
  PlusIcon,
  BinaryIcon,
  ChartScatterIcon,
} from "lucide-react";
import type { ChartType } from "./storage";
import type { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";

export const CHART_TYPE_ICON: Record<ChartType, React.ElementType> = {
  line: LineChartIcon,
  bar: BarChartIcon,
  pie: PieChartIcon,
  scatter: ChartScatterIcon,
};

export const AGGREGATION_TYPE_ICON: Record<
  (typeof AGGREGATION_FNS)[number],
  React.ElementType
> = {
  count: BinaryIcon,
  sum: SigmaIcon,
  mean: CircleSlash2,
  median: CircleSlash2,
  min: MinusIcon,
  max: PlusIcon,
};
