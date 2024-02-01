/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { FieldOptions } from "../forms/options";

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
  date: z.coerce.date().describe(FieldOptions.of({ label: "Value" })),
};

export const BOOLEAN_OPERATORS = {
  is_true: [],
  is_false: [],
};

export const NUMERIC_OPERATORS = {
  "==": [Schema.number],
  "!=": [Schema.number],
  ">": [Schema.number],
  ">=": [Schema.number],
  "<": [Schema.number],
  "<=": [Schema.number],
  is_nan: [],
  is_not_nan: [],
};

export const DATE_OPERATORS = {
  "==": [Schema.date],
  "!=": [Schema.date],
  ">": [Schema.date],
  ">=": [Schema.date],
  "<": [Schema.date],
  "<=": [Schema.date],
  is_nan: [],
  is_not_nan: [],
};

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
  ...STRING_OPERATORS,
};

export type OperatorType = keyof typeof ALL_OPERATORS;

export function getOperatorForDtype(dtype: string): readonly string[] {
  if (!dtype) {
    return [];
  }

  if (dtype === "bool") {
    return Object.keys(BOOLEAN_OPERATORS);
  } else if (dtype.startsWith("int") || dtype.startsWith("float")) {
    return Object.keys(NUMERIC_OPERATORS);
  } else if (dtype === "datetime64[ns]") {
    return Object.keys(DATE_OPERATORS);
  } else if (dtype === "object" || dtype === "string") {
    return Object.keys(STRING_OPERATORS);
  } else {
    return [];
  }
}

export function getSchemaForOperator(
  dtype: string,
  operator: string,
): [z.ZodType] | [] {
  if (!dtype || !operator) {
    return [];
  }

  if (dtype === "bool") {
    return safeGet(BOOLEAN_OPERATORS, operator);
  } else if (dtype.startsWith("int") || dtype.startsWith("float")) {
    return safeGet(NUMERIC_OPERATORS, operator);
  } else if (dtype === "datetime64[ns]") {
    return safeGet(DATE_OPERATORS, operator);
  } else if (dtype === "object" || dtype === "string") {
    return safeGet(STRING_OPERATORS, operator);
  } else {
    return [];
  }
}

export function isConditionValueValid(operator: string, value: unknown) {
  const possibleSchemas = [
    safeGet(BOOLEAN_OPERATORS, operator),
    safeGet(DATE_OPERATORS, operator),
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
