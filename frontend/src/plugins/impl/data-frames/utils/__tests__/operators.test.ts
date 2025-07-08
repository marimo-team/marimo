/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import {
  BOOLEAN_OPERATORS,
  DATE_OPERATORS,
  DATETIME_OPERATORS,
  getOperatorForDtype,
  getSchemaForOperator,
  isConditionValueValid,
  NUMERIC_OPERATORS,
  STRING_OPERATORS,
} from "../operators";

describe("getOperatorForDtype", () => {
  it('should return BOOLEAN_OPERATORS for "bool"', () => {
    expect(getOperatorForDtype("bool")).toEqual(Object.keys(BOOLEAN_OPERATORS));
    expect(getOperatorForDtype("boolean")).toEqual(
      Object.keys(BOOLEAN_OPERATORS),
    );
  });

  it('should return NUMERIC_OPERATORS for "int" and "float"', () => {
    expect(getOperatorForDtype("int")).toEqual(Object.keys(NUMERIC_OPERATORS));
    expect(getOperatorForDtype("number")).toEqual(
      Object.keys(NUMERIC_OPERATORS),
    );
    expect(getOperatorForDtype("float")).toEqual(
      Object.keys(NUMERIC_OPERATORS),
    );
  });

  it('should return DATE_OPERATORS for "datetime64[ns]"', () => {
    expect(getOperatorForDtype("datetime64[ns]")).toEqual(
      Object.keys(DATE_OPERATORS),
    );
    expect(getOperatorForDtype("date")).toEqual(Object.keys(DATE_OPERATORS));
    expect(getOperatorForDtype("datetime")).toEqual(
      Object.keys(DATE_OPERATORS),
    );
    expect(getOperatorForDtype("time")).toEqual(Object.keys(DATE_OPERATORS));
  });

  it('should return STRING_OPERATORS for "object" and "string"', () => {
    expect(getOperatorForDtype("object")).toEqual(
      Object.keys(STRING_OPERATORS),
    );
    expect(getOperatorForDtype("string")).toEqual(
      Object.keys(STRING_OPERATORS),
    );
  });

  it("should return empty array for bool", () => {
    expect(getOperatorForDtype("bool")).toEqual(Object.keys(BOOLEAN_OPERATORS));
    expect(getOperatorForDtype("boolean")).toEqual(
      Object.keys(BOOLEAN_OPERATORS),
    );
  });

  it("should return empty array for unknown dtype", () => {
    expect(getOperatorForDtype("unknown")).toEqual([]);
  });
});

describe("getSchemaForOperator", () => {
  it("should return the correct schema for the given dtype and operator", () => {
    expect(getSchemaForOperator("bool", "is true")).toEqual(
      BOOLEAN_OPERATORS.is_true,
    );
    expect(getSchemaForOperator("boolean", "is true")).toEqual(
      BOOLEAN_OPERATORS.is_true,
    );
    expect(getSchemaForOperator("int", "==")).toEqual(NUMERIC_OPERATORS["=="]);
    expect(getSchemaForOperator("number", "==")).toEqual(
      NUMERIC_OPERATORS["=="],
    );
    expect(getSchemaForOperator("datetime64[ns]", "!=")).toEqual(
      DATETIME_OPERATORS["!="],
    );
    expect(getSchemaForOperator("date", "!=")).toEqual(DATE_OPERATORS["!="]);
    expect(getSchemaForOperator("string", "contains")).toEqual(
      STRING_OPERATORS.contains,
    );
  });

  it("should return empty array for unknown dtype or operator", () => {
    expect(getSchemaForOperator("unknown", "==")).toEqual([]);
    expect(getSchemaForOperator("int", "unknown")).toEqual([]);
  });
});

describe("isConditionValueValid", () => {
  it("should return true if the value is valid according to the schema for the given operator", () => {
    expect(isConditionValueValid("is_true", true)).toBe(true);
    expect(isConditionValueValid("==", 123)).toBe(true);
    expect(isConditionValueValid("==", "12:34")).toBe(true);
    expect(isConditionValueValid("==", "12:34:56")).toBe(true);
    expect(isConditionValueValid("==", new Date("2024-01-01T12:34:56"))).toBe(
      true,
    );
    expect(isConditionValueValid("contains", "test")).toBe(true);
    expect(isConditionValueValid("in", ["test"])).toBe(true);
  });

  it("should return false if the value is not valid according to the schema for the given operator", () => {
    expect(isConditionValueValid("==", "not a number")).toBe(false);
    expect(isConditionValueValid("contains", 123)).toBe(false);
    expect(isConditionValueValid("in", "not an array")).toBe(false);
  });

  it("should return true if the operator does not require a value", () => {
    expect(isConditionValueValid("is_true", null)).toBe(true);
    expect(isConditionValueValid("is_null", undefined)).toBe(true);
    expect(isConditionValueValid("is_not_null", undefined)).toBe(true);
  });
});
