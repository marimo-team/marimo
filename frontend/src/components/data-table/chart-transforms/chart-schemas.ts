/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Zod schema validation for marimo chart configuration.
 */

import { DATA_TYPES } from "@/core/kernel/messages";
import { z } from "zod";
import {
  AGGREGATION_FNS,
  NONE_AGGREGATION,
  SELECTABLE_DATA_TYPES,
  SORT_TYPES,
  TIME_UNITS,
} from "./types";
import { DEFAULT_COLOR_SCHEME, EMPTY_VALUE } from "./constants";

export const DEFAULT_BIN_VALUE = 0;
export const NONE_GROUP_BY = "None";

export const BinSchema = z.object({
  binned: z.boolean().optional(),
  step: z.number().optional(),
});

export const AxisSchema = z
  .object({
    field: z.string().optional(),
    type: z.enum([...DATA_TYPES, EMPTY_VALUE]).optional(),
    selectedDataType: z
      .enum([...SELECTABLE_DATA_TYPES, EMPTY_VALUE])
      .optional(),
    aggregate: z.enum(AGGREGATION_FNS).default(NONE_AGGREGATION).optional(),
    sort: z.enum(SORT_TYPES).default("ascending").optional(),
    timeUnit: z.enum(TIME_UNITS).optional(),
  })
  .optional();

export const ChartSchema = z.object({
  general: z.object({
    title: z.string().optional(),
    xColumn: AxisSchema,
    yColumn: AxisSchema,
    colorByColumn: AxisSchema,
    horizontal: z.boolean().optional(),
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

export type ChartSchemaType = z.infer<typeof ChartSchema>;
