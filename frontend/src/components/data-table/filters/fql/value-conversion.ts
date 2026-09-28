/* Copyright 2026 Marimo. All rights reserved. */

import type { ScalarValue } from "better-filter-bar";
import { z } from "zod";
import { assertNever } from "@/utils/assertNever";
import type { FilterableDataType } from "./contracts";

export type ValueConversionResult<T> =
  | { ok: true; value: T }
  | { ok: false; reason: string };

export interface WildcardPattern {
  operator: "contains" | "starts_with" | "ends_with";
  value: string;
}

const INTEGER_PATTERN = /^[+-]?\d+$/;
const NUMBER_PATTERN = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const DATETIME_PATTERN =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?$/;
const TIME_PATTERN = /^\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$/;

const DATE_SCHEMA = z.iso.date();
const DATETIME_SCHEMA = z.iso
  .datetime({ offset: true, local: true })
  .regex(DATETIME_PATTERN);
const TIME_SCHEMA = z.iso.time().regex(TIME_PATTERN);

function invalidValue(reason: string): ValueConversionResult<never> {
  return { ok: false, reason };
}

function validValue<T>(value: T): ValueConversionResult<T> {
  return { ok: true, value };
}

function hasBackendSupportedYear(value: string): boolean {
  return !value.startsWith("0000-");
}

export function convertScalarValue(
  value: ScalarValue,
  dataType: FilterableDataType,
): ValueConversionResult<string | number> {
  const text = String(value.value);
  const reason = `Expected a valid ${dataType} value.`;

  switch (dataType) {
    case "string":
      return validValue(text);
    case "integer": {
      if (!INTEGER_PATTERN.test(text)) {
        return invalidValue(reason);
      }
      const number = Number(text);
      return Number.isSafeInteger(number)
        ? validValue(number)
        : invalidValue(reason);
    }
    case "number": {
      if (!NUMBER_PATTERN.test(text)) {
        return invalidValue(reason);
      }
      const number = Number(text);
      return Number.isFinite(number)
        ? validValue(number)
        : invalidValue(reason);
    }
    case "date":
      return DATE_SCHEMA.safeParse(text).success &&
        hasBackendSupportedYear(text)
        ? validValue(text)
        : invalidValue(reason);
    case "datetime":
      return DATETIME_SCHEMA.safeParse(text).success &&
        hasBackendSupportedYear(text)
        ? validValue(text)
        : invalidValue(reason);
    case "time":
      return TIME_SCHEMA.safeParse(text).success
        ? validValue(text)
        : invalidValue(reason);
    case "boolean":
      return invalidValue(reason);
    default:
      return assertNever(dataType);
  }
}

export function convertExactList(
  values: ScalarValue[],
  dataType: FilterableDataType,
): ValueConversionResult<Array<string | number>> {
  if (values.length === 0) {
    return invalidValue("Expected at least one list value.");
  }

  const converted: Array<string | number> = [];
  for (const value of values) {
    const result = convertScalarValue(value, dataType);
    if (!result.ok) {
      return result;
    }
    converted.push(result.value);
  }
  return validValue(converted);
}

export function decodeWildcardPattern(
  value: string,
): ValueConversionResult<WildcardPattern | undefined> {
  if (value === "*") {
    return invalidValue(
      "A lone star is ambiguous. Use two stars for an empty pattern.",
    );
  }

  const hasLeadingMarker = value.startsWith("*");
  let precedingBackslashes = 0;
  for (
    let index = value.length - 2;
    index >= 0 && value[index] === "\\";
    index--
  ) {
    precedingBackslashes++;
  }
  const hasTrailingMarker =
    value.endsWith("*") && precedingBackslashes % 2 === 0;

  if (!hasLeadingMarker && !hasTrailingMarker) {
    return validValue(undefined);
  }

  const start = hasLeadingMarker ? 1 : 0;
  const end = hasTrailingMarker ? value.length - 1 : value.length;
  const decodedValue = value.slice(start, end).replace(/\\([\\*])/g, "$1");
  const operator =
    hasLeadingMarker && hasTrailingMarker
      ? "contains"
      : hasLeadingMarker
        ? "ends_with"
        : "starts_with";

  return validValue({ operator, value: decodedValue });
}
