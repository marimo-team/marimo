/* Copyright 2024 Marimo. All rights reserved. */

import { DATA_TYPES } from "@/core/kernel/messages";
import { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";
import { z } from "zod";

export const DEFAULT_AGGREGATION = "default";
export const NONE_GROUP_BY = "None";

export const ChartSchema = z.object({
  general: z.object({
    title: z.string().optional(),
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
    horizontal: z.boolean().optional(),
    groupByColumn: z
      .object({
        field: z.string().default(NONE_GROUP_BY).optional(),
        type: z.enum(DATA_TYPES).optional(),
      })
      .optional(),
    stacking: z.boolean().optional(),
    tooltips: z
      .array(
        z.object({
          field: z.string(),
          type: z.enum(DATA_TYPES),
        }),
      )
      .optional(),
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
