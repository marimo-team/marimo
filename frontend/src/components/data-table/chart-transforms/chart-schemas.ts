/* Copyright 2024 Marimo. All rights reserved. */

import { DATA_TYPES } from "@/core/kernel/messages";
import { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";
import { z } from "zod";

export const DEFAULT_AGGREGATION = "default";
export const DEFAULT_BIN_VALUE = 0;
export const NONE_GROUP_BY = "None";
export const DEFAULT_COLOR_SCHEME = "default";

// These data types can be selected to override the default data type
export const SELECTABLE_DATA_TYPES = ["number", "string", "temporal"] as const;
export type SelectableDataType = (typeof SELECTABLE_DATA_TYPES)[number];

export const SORT_TYPES = ["ascending", "descending"] as const;

export const TIME_UNITS = [
  "year",
  "quarter",
  "month",
  "week",
  "day",
  "hours",
  "minutes",
  "seconds",
] as const;
export type TimeUnit = (typeof TIME_UNITS)[number];

export const BinSchema = z.object({
  binned: z.boolean().optional(),
  step: z.number().optional(),
});

export const ChartSchema = z.object({
  general: z.object({
    title: z.string().optional(),
    xColumn: z
      .object({
        field: z.string().optional(),
        type: z.enum(DATA_TYPES).optional(),
        selectedDataType: z.enum(SELECTABLE_DATA_TYPES).optional(),
        sort: z.enum(SORT_TYPES).default("ascending").optional(),
        agg: z
          .enum([...AGGREGATION_FNS, DEFAULT_AGGREGATION])
          .default(DEFAULT_AGGREGATION)
          .optional(),
        timeUnit: z.enum(TIME_UNITS).optional(),
      })
      .optional(),
    yColumn: z
      .object({
        field: z.string().optional(),
        type: z.enum(DATA_TYPES).optional(),
        selectedDataType: z.enum(SELECTABLE_DATA_TYPES).optional(),
        agg: z
          .enum([...AGGREGATION_FNS, DEFAULT_AGGREGATION])
          .default(DEFAULT_AGGREGATION)
          .optional(),
        timeUnit: z.enum(TIME_UNITS).optional(),
      })
      .optional(),
    horizontal: z.boolean().optional(),
    colorByColumn: z
      .object({
        field: z.string().optional(),
        type: z.enum(DATA_TYPES).optional(),
        selectedDataType: z.enum(SELECTABLE_DATA_TYPES).optional(),
        binned: z.boolean().optional(),
        agg: z
          .enum([...AGGREGATION_FNS, DEFAULT_AGGREGATION])
          .default(DEFAULT_AGGREGATION)
          .optional(),
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
      width: z.number().optional(),
      bin: BinSchema.optional(),
    })
    .optional(),
  yAxis: z
    .object({
      label: z.string().optional(),
      height: z.number().optional(),
      bin: BinSchema.optional(),
    })
    .optional(),
  color: z
    .object({
      scheme: z.string().default(DEFAULT_COLOR_SCHEME).optional(),
      range: z.array(z.string()).optional(),
      domain: z.array(z.string()).optional(),
    })
    .optional(),
  style: z
    .object({
      innerRadius: z.number().optional(),
    })
    .optional(),
});
