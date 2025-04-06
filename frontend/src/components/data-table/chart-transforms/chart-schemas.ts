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

export const ChartSchema = BaseChartSchema.extend({
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
  }),
});

export const PieChartSchema = BaseChartSchema.extend({
  general: z.object({
    theta: z
      .object({
        name: z.string().optional(),
        type: z.enum(DATA_TYPES).optional(),
      })
      .optional(),
    color: z.object({
      name: z.string().optional(),
      type: z.enum(DATA_TYPES).optional(),
    }),
  }),
});
