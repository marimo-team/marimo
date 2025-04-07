/* Copyright 2024 Marimo. All rights reserved. */

import { DATA_TYPES } from "@/core/kernel/messages";
import { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";
import { z } from "zod";
import { DEFAULT_AGGREGATION } from "./chart-spec";

const axisSchema = {
  xAxis: z
    .object({
      label: z.string().optional(),
    })
    .optional(),
  yAxis: z
    .object({
      label: z.string().optional(),
    })
    .optional(),
};

const BaseChartSchema = z.object({
  general: z.object({}).passthrough(),
  ...axisSchema,
});

export const ChartSchema = z.object({
  general: z.object({
    xColumn: z.object({
      field: z.string().optional(),
      type: z.enum(DATA_TYPES).optional(),
    }),
    yColumn: z.object({
      field: z.string().optional(),
      type: z.enum(DATA_TYPES).optional(),
      agg: z
        .enum([...AGGREGATION_FNS, DEFAULT_AGGREGATION])
        .default(DEFAULT_AGGREGATION)
        .optional(),
    }),
    tooltips: z.array(z.string()).optional(),
  }),
  xAxis: z
    .object({
      label: z.string().optional(),
    })
    .optional(),
  yAxis: z
    .object({
      label: z.string().optional(),
    })
    .optional(),
});
