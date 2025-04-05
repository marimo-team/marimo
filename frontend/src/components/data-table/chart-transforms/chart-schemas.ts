/* Copyright 2024 Marimo. All rights reserved. */

import { DATA_TYPES } from "@/core/kernel/messages";
import { z } from "zod";

export const LineChartSchema = z.object({
  general: z.object({
    // xColumn: z.string().nullable(),
    xColumn: z.object({
      name: z.string(),
      type: z.enum(DATA_TYPES),
    }),
    yColumn: z.string().nullable(),
  }),
  xAxis: z.object({
    label: z.string().nullable(),
  }),
  yAxis: z.object({
    label: z.string().nullable(),
  }),
});
