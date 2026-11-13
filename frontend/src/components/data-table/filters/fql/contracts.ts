/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";
import { DATA_TYPES } from "@/core/kernel/messages";
import {
  FilterConditionSchema,
  FilterGroupSchema,
  type FilterGroupType,
} from "@/plugins/impl/data-frames/schema";

/**
 * Runtime contracts for the FQL adapter and its shared JSON data.
 *
 * The main data flow is: FQL text + FqlColumn[] -> adapter -> FqlAdapterResult.
 * The catalog and conformance suite are supporting data, not new native filter models.
 */

/** Marimo data types that have defined FQL operations. */
export const FilterableDataTypeSchema = z
  .enum(DATA_TYPES)
  .exclude(["geometry", "unknown"]);
export const FILTERABLE_DATA_TYPES = FilterableDataTypeSchema.options;
export type FilterableDataType = z.infer<typeof FilterableDataTypeSchema>;

/**
 * Column metadata that the adapter needs to resolve one FQL field.
 *
 * `alias` is the parser-safe field name. `column_id` is the original table
 * column that the native filter group receives.
 */
export const FqlColumnSchema = z.object({
  column_id: z.union([z.string().min(1), z.number()]),
  alias: z
    .string()
    .regex(/^[A-Za-z_][A-Za-z0-9_]*$/, "Must be an FQL-safe identifier"),
  data_type: FilterableDataTypeSchema,
});
export type FqlColumn = z.infer<typeof FqlColumnSchema>;

/**
 * One operation that the adapter can translate from FQL to a native filter.
 *
 * The syntax fields describe the FQL form. The native fields define the
 * target operator and its supported column types.
 */
const TableFilterOperationIdSchema = z.enum([
  "exact_text",
  "not_exact_text",
  "contains_text",
  "starts_with_text",
  "ends_with_text",
  "regex_text",
  "contains_empty_text",
  "empty_text",
  "scalar_equal",
  "scalar_not_equal",
  "greater_than",
  "greater_than_or_equal",
  "less_than",
  "less_than_or_equal",
  "in_list",
  "not_in_list",
  "is_null",
  "is_not_null",
  "boolean_true",
  "boolean_false",
]);
export type TableFilterOperationId = z.infer<
  typeof TableFilterOperationIdSchema
>;

const TableFilterOperationSchema = z.object({
  id: TableFilterOperationIdSchema,
  fql_form: z.string().min(1),
  example: z.string().min(1),
  native_operator: FilterConditionSchema.shape.operator,
  supported_types: z.array(FilterableDataTypeSchema).min(1),
  meaning: z.string().min(1),
});

/** Runtime schema for `table_filter_operation_catalog.json`. */
export const TableFilterOperationCatalogSchema = z.object({
  version: z.literal(1),
  operations: z.array(TableFilterOperationSchema).min(1),
});

const ConformanceValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);

const TableFilterConformanceRowSchema = z.object({
  row_id: z.string().min(1),
  values: z.record(z.string(), ConformanceValueSchema),
});

/**
 * One end-to-end example on the fixed table in the conformance suite.
 *
 * `expected_filter` is hand-written. `expected_row_ids` proves that the native
 * filter has the requested behavior.
 */
const TableFilterConformanceCaseSchema = z.object({
  id: z.string().regex(/^[a-z][a-z0-9_]*$/),
  request: z.string().min(1),
  fql: z.string().min(1),
  operation_ids: z.array(TableFilterOperationIdSchema).min(1),
  expected_filter: FilterGroupSchema,
  expected_row_ids: z.array(z.string()),
});

/**
 * Runtime schema for `table_filter_conformance_cases.json`.
 *
 * The adapter does not read this file at runtime. Tests use the complete suite.
 * Later prompt and notebook work can reuse selected cases.
 */
export const TableFilterConformanceSuiteSchema = z.object({
  version: z.literal(1),
  table: z.object({
    columns: z.array(FqlColumnSchema).min(1),
    rows: z.array(TableFilterConformanceRowSchema).min(1),
  }),
  cases: z.array(TableFilterConformanceCaseSchema).min(1),
});

/**
 * Public result from FQL conversion.
 *
 * Successful results contain the native filter group that table search accepts.
 * Rejections contain a reason that the caller can display.
 */
export type FqlAdapterResult =
  | { ok: true; filter: FilterGroupType }
  | { ok: false; reason: string };
