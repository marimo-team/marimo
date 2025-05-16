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

export const BinSchema = z.object({
  binned: z.boolean().optional(),
  step: z.number().optional(),
  maxbins: z.number().optional(),
});

const BaseColumnSchema = z.object({
  field: z.string().optional(),
  type: z.enum([...DATA_TYPES, EMPTY_VALUE]).optional(),
  selectedDataType: z.enum([...SELECTABLE_DATA_TYPES, EMPTY_VALUE]).optional(),
  sort: z.enum(SORT_TYPES).default("ascending").optional(),
  timeUnit: z.enum(TIME_UNITS).optional(),
});

export const AxisSchema = BaseColumnSchema.extend({
  aggregate: z.enum(AGGREGATION_FNS).default(NONE_AGGREGATION).optional(),
});

export const RowFacet = BaseColumnSchema.extend({
  linkYAxis: z.boolean().default(true).optional(),
  binned: z.boolean().default(true).optional(),
  maxbins: z.number().optional(),
});
export const ColumnFacet = BaseColumnSchema.extend({
  linkXAxis: z.boolean().default(true).optional(),
  binned: z.boolean().default(true).optional(),
  maxbins: z.number().optional(),
});

export const ChartSchema = z.object({
  general: z
    .object({
      title: z.string().optional(),
      xColumn: AxisSchema.optional(),
      yColumn: AxisSchema.optional(),
      colorByColumn: AxisSchema.optional(),
      facet: z
        .object({
          row: RowFacet,
          column: ColumnFacet,
        })
        .optional(),
      horizontal: z.boolean().optional(),
      stacking: z.boolean().optional(),
    })
    .optional(),
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
      bin: BinSchema.optional(),
    })
    .optional(),
  style: z
    .object({
      innerRadius: z.number().optional(),
    })
    .optional(),
  tooltips: z
    .object({
      auto: z.boolean(),
      fields: z.array(
        z.object({
          field: z.string(),
          type: z.enum(DATA_TYPES),
        }),
      ),
    })
    .default({ auto: true, fields: [] })
    .optional(),
});

export type ChartSchemaType = z.infer<typeof ChartSchema>;
