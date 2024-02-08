/* Copyright 2024 Marimo. All rights reserved. */
import {
  AGGREGATION_FNS,
  NUMPY_DTYPES,
} from "@/plugins/impl/data-frames/types";
import {
  FieldOptions,
  randomNumber,
} from "@/plugins/impl/data-frames/forms/options";
import { z } from "zod";
import {
  ALL_OPERATORS,
  OperatorType,
  isConditionValueValid,
} from "./utils/operators";

const column_id = z
  .string()
  .min(1, "Required")
  .describe(FieldOptions.of({ label: "Column", special: "column_id" }));

const column_id_array = z
  .array(column_id.describe(FieldOptions.of({ special: "column_id" })))
  .min(1, "At least one column is required")
  .default([])
  .describe(FieldOptions.of({ label: "Columns" }));

const ColumnConversionTransformSchema = z
  .object({
    type: z.literal("column_conversion"),
    column_id: column_id,
    data_type: z
      .enum(NUMPY_DTYPES)
      .describe(FieldOptions.of({ label: "Data type (numpy)" }))
      .default("bool"),
    errors: z
      .enum(["ignore", "raise"])
      .default("ignore")
      .describe(
        FieldOptions.of({ label: "Handle errors", special: "radio_group" }),
      ),
  })
  .describe(FieldOptions.of({}));

const RenameColumnTransformSchema = z.object({
  type: z.literal("rename_column"),
  column_id: column_id,
  new_column_id: z
    .string()
    .min(1, "Required")
    .describe(FieldOptions.of({ label: "New column name" })),
});

const SortColumnTransformSchema = z.object({
  type: z.literal("sort_column"),
  column_id: column_id,
  ascending: z
    .boolean()
    .describe(FieldOptions.of({ label: "Ascending" }))
    .default(true),
  na_position: z
    .enum(["first", "last"])
    .describe(
      FieldOptions.of({ label: "N/A position", special: "radio_group" }),
    )
    .default("last"),
});

export const ConditionSchema = z
  .object({
    column_id: column_id,
    operator: z
      .enum(Object.keys(ALL_OPERATORS) as [OperatorType, ...OperatorType[]])
      .describe(FieldOptions.of({ label: " " })),
    value: z.any().describe(FieldOptions.of({ label: "Value" })),
  })
  .describe(FieldOptions.of({ direction: "row", special: "column_filter" }));

const FilterRowsTransformSchema = z.object({
  type: z.literal("filter_rows"),
  operation: z
    .enum(["keep_rows", "remove_rows"])
    .default("keep_rows")
    .describe(FieldOptions.of({ special: "radio_group" })),
  where: z
    .array(ConditionSchema)
    .min(1)
    .transform((value) => {
      return value.filter((condition) => {
        return isConditionValueValid(condition.operator, condition.value);
      });
    })
    .describe(FieldOptions.of({ label: "Value" }))
    .default([{ column_id: "", operator: "==", value: "" }]),
});

const GroupByTransformSchema = z
  .object({
    type: z.literal("group_by"),
    column_ids: column_id_array,
    aggregation: z
      .enum(AGGREGATION_FNS)
      .default("count")
      .describe(FieldOptions.of({ label: "Aggregation" })),
    drop_na: z
      .boolean()
      .default(false)
      .describe(FieldOptions.of({ label: "Drop N/A" })),
  })
  .describe(FieldOptions.of({}));

const AggregateTransformSchema = z
  .object({
    type: z.literal("aggregate"),
    column_ids: column_id_array,
    aggregations: z
      .array(z.enum(AGGREGATION_FNS))
      .min(1, "At least one aggregation is required")
      .default(["count"])
      .describe(FieldOptions.of({ label: "Aggregations" })),
  })
  .describe(FieldOptions.of({ direction: "row" }));

const SelectColumnsTransformSchema = z.object({
  type: z.literal("select_columns"),
  column_ids: column_id_array,
});

const SampleRowsTransformSchema = z.object({
  type: z.literal("sample_rows"),
  n: z
    .number()
    .positive()
    .describe(FieldOptions.of({ label: "Number of rows" })),
  seed: z
    .number()
    .default(() => randomNumber())
    .describe(
      FieldOptions.of({ label: "Re-sample", special: "random_number_button" }),
    ),
  replace: z
    .boolean()
    .default(false)
    .describe(
      FieldOptions.of({
        label: "Sample with replacement",
      }),
    ),
});

const ShuffleRowsTransformSchema = z.object({
  type: z.literal("shuffle_rows"),
  seed: z
    .number()
    .default(() => randomNumber())
    .describe(
      FieldOptions.of({ label: "Re-shuffle", special: "random_number_button" }),
    ),
});

export const TransformTypeSchema = z.union([
  FilterRowsTransformSchema,
  SelectColumnsTransformSchema,
  RenameColumnTransformSchema,
  ColumnConversionTransformSchema,
  SortColumnTransformSchema,
  GroupByTransformSchema,
  AggregateTransformSchema,
  SampleRowsTransformSchema,
  ShuffleRowsTransformSchema,
]);

export type TransformType = z.infer<typeof TransformTypeSchema>;

export const TransformationsSchema = z.object({
  transforms: z.array(TransformTypeSchema),
});

export type Transformations = z.infer<typeof TransformationsSchema>;
