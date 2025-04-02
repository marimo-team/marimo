/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";

export const LineChartSchema = z.object({
  general: z.object({
    xColumn: z.string(),
    yColumn: z.string(),
  }),
  xAxis: z.object({
    label: z.string(),
  }),
  yAxis: z.object({
    label: z.string(),
  }),
});
