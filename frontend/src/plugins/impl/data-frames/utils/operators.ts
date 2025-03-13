/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { FieldOptions } from "../../../../components/forms/options";
import type { DataType } from "@/core/kernel/messages";

const Schema = {
  number: z.coerce.number().describe(FieldOptions.of({ label: "Value" })),
  string: z
    .string()
    .min(1)
    .describe(FieldOptions.of({ label: "Value" })),
  stringColumnValues: z
    .string()
    .min(1)
    .describe(FieldOptions.of({ label: "Value", special: "column_values" })),
  stringMultiColumnValues: z
    .array(z.string())
    .min(1)
    .describe(FieldOptions.of({ label: "Value", special: "column_values" })),
  date: z.coerce
    .date()
    .describe(FieldOptions.of({ label: "Value", special: "date" })),
  datetime: z.coerce
    .date()
    .describe(FieldOptions.of({ label: "Value", special: "datetime" })),
  time: z
    .string()
    .regex(/^\d{2}:\d{2}(:\d{2})?$/)
    .describe(FieldOptions.of({ label: "Value", special: "time" })),
};

export const BOOLEAN_OPERATORS = {
  is_true: [],
  is_false: [],
};

const createComparisonOperators = (schema: z.ZodType) => ({
  "==": [schema],
  "!=": [schema],
  ">": [schema],
  ">=": [schema],
  "<": [schema],
  "<=": [schema],
  is_nan: [],
  is_not_nan: [],
});

export const NUMERIC_OPERATORS = createComparisonOperators(Schema.number);
export const DATE_OPERATORS = createComparisonOperators(Schema.date);
export const TIME_OPERATORS = createComparisonOperators(Schema.time);
export const DATETIME_OPERATORS = createComparisonOperators(Schema.datetime);

export const STRING_OPERATORS = {
  equals: [Schema.stringColumnValues],
  does_not_equal: [Schema.stringColumnValues],
  contains: [Schema.string],
  regex: [Schema.string],
  starts_with: [Schema.string],
  ends_with: [Schema.string],
  in: [Schema.stringMultiColumnValues],
};

export const ALL_OPERATORS = {
  ...BOOLEAN_OPERATORS,
  ...NUMERIC_OPERATORS,
  ...DATE_OPERATORS,
  ...TIME_OPERATORS,
  ...DATETIME_OPERATORS,
  ...STRING_OPERATORS,
};

export type OperatorType = keyof typeof ALL_OPERATORS;

function numpyTypeToDataType(type: string): DataType {
  if (!type) {
    return "unknown";
  }

  if (type.startsWith("int")) {
    return "integer";
  }

  if (
    type.startsWith("float") ||
    type.startsWith("uint") ||
    type.startsWith("number") ||
    type.startsWith("complex")
  ) {
    return "number";
  }

  if (
    type.startsWith("string") ||
    type.startsWith("object") ||
    type.startsWith("utf8")
  ) {
    return "string";
  }

  if (type.startsWith("datetime")) {
    return "datetime";
  }

  if (type.startsWith("time")) {
    return "time";
  }

  if (type.startsWith("date")) {
    return "date";
  }

  if (type.startsWith("bool")) {
    return "boolean";
  }

  return "unknown";
}

export function getOperatorForDtype(
  dtype: string | undefined,
): readonly string[] {
  if (!dtype) {
    return [];
  }

  const dataType = numpyTypeToDataType(dtype);

  switch (dataType) {
    case "integer":
      return Object.keys(NUMERIC_OPERATORS);
    case "number":
      return Object.keys(NUMERIC_OPERATORS);
    case "string":
      return Object.keys(STRING_OPERATORS);
    case "date":
      return Object.keys(DATE_OPERATORS);
    case "datetime":
      return Object.keys(DATETIME_OPERATORS);
    case "time":
      return Object.keys(TIME_OPERATORS);
    case "boolean":
      return Object.keys(BOOLEAN_OPERATORS);
    case "unknown":
      return [];
  }
}

export function getSchemaForOperator(
  dtype: string | undefined,
  operator: string,
): [z.ZodType] | [] {
  if (!dtype || !operator) {
    return [];
  }

  const dataType = numpyTypeToDataType(dtype);

  switch (dataType) {
    case "integer":
      return safeGet(NUMERIC_OPERATORS, operator);
    case "number":
      return safeGet(NUMERIC_OPERATORS, operator);
    case "string":
      return safeGet(STRING_OPERATORS, operator);
    case "date":
      return safeGet(DATE_OPERATORS, operator);
    case "datetime":
      return safeGet(DATETIME_OPERATORS, operator);
    case "time":
      return safeGet(TIME_OPERATORS, operator);
    case "boolean":
      return safeGet(BOOLEAN_OPERATORS, operator);
    case "unknown":
      return [];
  }
}

export function isConditionValueValid(operator: string, value: unknown) {
  const possibleSchemas = [
    safeGet(BOOLEAN_OPERATORS, operator),
    safeGet(DATE_OPERATORS, operator),
    safeGet(TIME_OPERATORS, operator),
    safeGet(DATETIME_OPERATORS, operator),
    safeGet(NUMERIC_OPERATORS, operator),
    safeGet(STRING_OPERATORS, operator),
  ].flat();

  if (possibleSchemas.length === 0) {
    return true;
  }
  return possibleSchemas.some((schema) => schema.safeParse(value).success);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const safeGet = (obj: any, key: string): [z.ZodType] | [] => {
  if (obj[key]) {
    return obj[key];
  }
  return [];
};
