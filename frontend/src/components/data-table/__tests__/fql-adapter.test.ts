/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { adaptFqlFilter, type FqlColumn } from "../filters/fql";

const COLUMNS = [
  {
    column_id: "vehicle make",
    alias: "vehicle_make",
    data_type: "string",
  },
  { column_id: "active", alias: "active", data_type: "boolean" },
  { column_id: "quantity", alias: "quantity", data_type: "integer" },
  { column_id: "price", alias: "price", data_type: "number" },
  { column_id: "order date", alias: "order_date", data_type: "date" },
  {
    column_id: "created at",
    alias: "created_at",
    data_type: "datetime",
  },
  {
    column_id: "dispatch time",
    alias: "dispatch_time",
    data_type: "time",
  },
] satisfies FqlColumn[];

function expectedCondition(
  columnId: string,
  operator: string,
  value?: unknown,
): unknown {
  return {
    ok: true,
    filter: {
      type: "group",
      operator: "and",
      children: [
        {
          type: "condition",
          column_id: columnId,
          operator,
          ...(value === undefined ? {} : { value }),
          negate: false,
        },
      ],
      negate: false,
    },
  };
}

describe("adaptFqlFilter", () => {
  it.each([
    {
      name: "exact text",
      query: 'vehicle_make="chevy*deluxe"',
      operator: "equals",
      value: "chevy*deluxe",
    },
    {
      name: "literal slash text",
      query: 'vehicle_make="/chev/"',
      operator: "equals",
      value: "/chev/",
    },
    {
      name: "literal null text",
      query: 'vehicle_make="null"',
      operator: "equals",
      value: "null",
    },
    {
      name: "unequal text",
      query: 'vehicle_make!="ford"',
      operator: "does_not_equal",
      value: "ford",
    },
    {
      name: "colon exact text",
      query: 'vehicle_make:"chevrolet"',
      operator: "equals",
      value: "chevrolet",
    },
    {
      name: "contains text",
      query: 'vehicle_make:"*chev*"',
      operator: "contains",
      value: "chev",
    },
    {
      name: "starts with text",
      query: 'vehicle_make:"chev*"',
      operator: "starts_with",
      value: "chev",
    },
    {
      name: "ends with text",
      query: 'vehicle_make:"*let"',
      operator: "ends_with",
      value: "let",
    },
    {
      name: "regular expression",
      query: String.raw`vehicle_make:"/^chev\\d+$/"`,
      operator: "regex",
      value: String.raw`^chev\d+$`,
    },
    {
      name: "contains empty text",
      query: 'vehicle_make:"**"',
      operator: "contains",
      value: "",
    },
    {
      name: "empty text",
      query: 'vehicle_make:""',
      operator: "is_empty",
    },
    {
      name: "missing text",
      query: "vehicle_make:null",
      operator: "is_null",
    },
    {
      name: "quoted missing text",
      query: 'vehicle_make:"null"',
      operator: "is_null",
    },
    {
      name: "literal leading star in a prefix",
      query: String.raw`vehicle_make:"\\*chev*"`,
      operator: "starts_with",
      value: "*chev",
    },
    {
      name: "literal trailing star in a suffix",
      query: String.raw`vehicle_make:"*chev\\*"`,
      operator: "ends_with",
      value: "chev*",
    },
    {
      name: "literal backslash in contains text",
      query: String.raw`vehicle_make:"*\\\\*"`,
      operator: "contains",
      value: "\\",
    },
  ])("converts $name", ({ query, operator, value }) => {
    expect(adaptFqlFilter(query, COLUMNS)).toEqual(
      expectedCondition("vehicle make", operator, value),
    );
  });

  it("resolves aliases without case sensitivity", () => {
    expect(adaptFqlFilter('VEHICLE_MAKE="ford"', COLUMNS)).toEqual(
      expectedCondition("vehicle make", "equals", "ford"),
    );
  });

  it.each([
    ['quantity="-4"', "quantity", -4],
    ['price="-1.25e2"', "price", -125],
  ])("converts the numeric value in %s", (query, columnId, expected) => {
    expect(adaptFqlFilter(query, COLUMNS)).toEqual(
      expectedCondition(columnId, "==", expected),
    );
  });

  it.each([
    {
      dataType: "integer",
      alias: "quantity",
      columnId: "quantity",
      source: "4",
      expected: 4,
    },
    {
      dataType: "number",
      alias: "price",
      columnId: "price",
      source: "4.5",
      expected: 4.5,
    },
    {
      dataType: "date",
      alias: "order_date",
      columnId: "order date",
      source: '"2026-09-12"',
      expected: "2026-09-12",
    },
    {
      dataType: "datetime",
      alias: "created_at",
      columnId: "created at",
      source: '"2026-09-12T14:30:00.123+05:30"',
      expected: "2026-09-12T14:30:00.123+05:30",
    },
    {
      dataType: "time",
      alias: "dispatch_time",
      columnId: "dispatch time",
      source: '"10:30:00.123"',
      expected: "10:30:00.123",
    },
  ])(
    "converts every comparison for $dataType",
    ({ alias, columnId, source, expected }) => {
      const operators = [
        ["=", "=="],
        ["!=", "!="],
        [">", ">"],
        [">=", ">="],
        ["<", "<"],
        ["<=", "<="],
      ];
      for (const [fqlOperator, nativeOperator] of operators) {
        expect(
          adaptFqlFilter(`${alias}${fqlOperator}${source}`, COLUMNS),
        ).toEqual(expectedCondition(columnId, nativeOperator, expected));
      }
    },
  );

  it.each([
    ["vehicle_make", "vehicle make"],
    ["active", "active"],
    ["quantity", "quantity"],
    ["price", "price"],
    ["order_date", "order date"],
    ["created_at", "created at"],
    ["dispatch_time", "dispatch time"],
  ])("converts null for %s", (alias, columnId) => {
    expect(adaptFqlFilter(`${alias}:null`, COLUMNS)).toEqual(
      expectedCondition(columnId, "is_null"),
    );
  });

  it.each([
    {
      name: "text membership",
      query: 'vehicle_make:("chevrolet","ford")',
      columnId: "vehicle make",
      values: ["chevrolet", "ford"],
    },
    {
      name: "integer membership",
      query: "quantity:(1,2)",
      columnId: "quantity",
      values: [1, 2],
    },
    {
      name: "number membership",
      query: "price:(1.5,2.5)",
      columnId: "price",
      values: [1.5, 2.5],
    },
  ])("converts $name", ({ query, columnId, values }) => {
    expect(adaptFqlFilter(query, COLUMNS)).toEqual(
      expectedCondition(columnId, "in", values),
    );
  });

  it.each([
    ["active:true", "is_true"],
    ["active:false", "is_false"],
  ])("converts %s", (query, operator) => {
    expect(adaptFqlFilter(query, COLUMNS)).toEqual(
      expectedCondition("active", operator),
    );
  });

  it.each([
    ["", "Enter a filter."],
    ["chevrolet", "Use a column alias and an operation."],
    ["quantity>>4", "The filter has invalid FQL syntax."],
    ["missing=4", "Unknown column alias: missing."],
    [
      "vehicle_make>4",
      'The string column "vehicle make" does not support this operation.',
    ],
    ['quantity="4.5"', "Expected a valid integer value."],
    ["quantity=9007199254740992", "Expected a valid integer value."],
    ['price="NaN"', "Expected a valid number value."],
    ['order_date="2026-02-30"', "Expected a valid date value."],
    ['created_at="2026-09-12T25:00:00"', "Expected a valid datetime value."],
    ['created_at="2026-09-12T14:30"', "Expected a valid datetime value."],
    [
      'created_at="2026-09-12T14:30:00.1234567890"',
      "Expected a valid datetime value.",
    ],
    ['dispatch_time="10:60:00"', "Expected a valid time value."],
    ['dispatch_time="10:30"', "Expected a valid time value."],
    ["active:yes", "Expected the boolean value true or false."],
    ['vehicle_make:"//"', "A regular expression must contain a pattern."],
    [
      'vehicle_make:"*"',
      "A lone star is ambiguous. Use two stars for an empty pattern.",
    ],
    [
      'order_date:("2026-09-12","2026-09-13")',
      'The date column "order date" does not support this operation.',
    ],
    ["NOT vehicle_make:null", "NOT filters are not supported."],
    ["quantity=1 AND price=2", "Boolean filter groups are not supported."],
  ])("rejects %s", (query, reason) => {
    expect(adaptFqlFilter(query, COLUMNS)).toEqual({ ok: false, reason });
  });

  it("rejects invalid column metadata", () => {
    expect(adaptFqlFilter("quantity=1", [])).toEqual({
      ok: false,
      reason: "Column metadata is invalid.",
    });
  });

  it("rejects aliases that collide without case sensitivity", () => {
    expect(
      adaptFqlFilter("quantity=1", [
        ...COLUMNS,
        { column_id: "other quantity", alias: "Quantity", data_type: "number" },
      ]),
    ).toEqual({
      ok: false,
      reason: "Column aliases must be unique, ignoring case: Quantity.",
    });
  });
});
