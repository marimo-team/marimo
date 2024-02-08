/* Copyright 2024 Marimo. All rights reserved. */

import { expect, describe, it } from "vitest";
import {
  getOperatorForDtype,
  getSchemaForOperator,
  isConditionValueValid,
  BOOLEAN_OPERATORS,
  DATE_OPERATORS,
  NUMERIC_OPERATORS,
  STRING_OPERATORS,
} from "../operators";

describe("getOperatorForDtype", () => {
  it('should return BOOLEAN_OPERATORS for "bool"', () => {
    expect(getOperatorForDtype("bool")).toEqual(Object.keys(BOOLEAN_OPERATORS));
  });

  it('should return NUMERIC_OPERATORS for "int" and "float"', () => {
    expect(getOperatorForDtype("int")).toEqual(Object.keys(NUMERIC_OPERATORS));
    expect(getOperatorForDtype("float")).toEqual(
      Object.keys(NUMERIC_OPERATORS),
    );
  });

  it('should return DATE_OPERATORS for "datetime64[ns]"', () => {
    expect(getOperatorForDtype("datetime64[ns]")).toEqual(
      Object.keys(DATE_OPERATORS),
    );
  });

  it('should return STRING_OPERATORS for "object" and "string"', () => {
    expect(getOperatorForDtype("object")).toEqual(
      Object.keys(STRING_OPERATORS),
    );
    expect(getOperatorForDtype("string")).toEqual(
      Object.keys(STRING_OPERATORS),
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
    expect(getSchemaForOperator("int", "==")).toEqual(NUMERIC_OPERATORS["=="]);
    expect(getSchemaForOperator("datetime64[ns]", "!=")).toEqual(
      DATE_OPERATORS["!="],
    );
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
    expect(isConditionValueValid("is_nan", undefined)).toBe(true);
  });
});
