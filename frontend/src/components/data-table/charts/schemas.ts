/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Zod schema validation for marimo chart configuration.
 */

import { z } from "zod";
import { DATA_TYPES } from "@/core/kernel/messages";
import {
  DEFAULT_COLOR_SCHEME,
  DEFAULT_MAX_BINS_FACET,
  EMPTY_VALUE,
} from "./constants";
import {
  AGGREGATION_FNS,
  COLOR_BY_FIELDS,
  NONE_VALUE,
  SELECTABLE_DATA_TYPES,
  SORT_TYPES,
  TIME_UNITS,
} from "./types";

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
  aggregate: z.enum(AGGREGATION_FNS).default(NONE_VALUE).optional(),
});

export const RowFacet = BaseColumnSchema.extend({
  linkYAxis: z.boolean().default(true),
  binned: z.boolean().default(true),
  maxbins: z.number().default(DEFAULT_MAX_BINS_FACET),
});

export const ColumnFacet = BaseColumnSchema.extend({
  linkXAxis: z.boolean().default(true),
  binned: z.boolean().default(true),
  maxbins: z.number().default(DEFAULT_MAX_BINS_FACET),
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
      field: z.enum([...COLOR_BY_FIELDS, NONE_VALUE]).default(NONE_VALUE),
      scheme: z.string().default(DEFAULT_COLOR_SCHEME).optional(),
      range: z.array(z.string()).optional(),
      domain: z.array(z.string()).optional(),
      bin: BinSchema.optional(),
    })
    .optional(),
  style: z
    .object({
      innerRadius: z.number().optional(),
      gridLines: z.boolean().optional(),
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

export function getChartDefaults(): ChartSchemaType {
  return {
    general: {
      facet: {
        row: {
          linkYAxis: true,
          binned: true,
          maxbins: DEFAULT_MAX_BINS_FACET,
        },
        column: {
          linkXAxis: true,
          binned: true,
          maxbins: DEFAULT_MAX_BINS_FACET,
        },
      },
    },
    color: {
      field: NONE_VALUE,
      scheme: "default",
    },
    tooltips: {
      auto: true,
      fields: [],
    },
  };
}
