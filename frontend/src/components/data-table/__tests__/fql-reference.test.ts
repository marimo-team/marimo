/* Copyright 2026 Marimo. All rights reserved. */

import { fqlLanguage } from "better-filter-bar";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import operationCatalogJson from "../../../../../marimo/_server/ai/table_filter_operation_catalog.json";
import { FilterConditionSchema } from "@/plugins/impl/data-frames/schema";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { adaptFqlFilter } from "../filters/fql/adapter";
import {
  FILTERABLE_DATA_TYPES,
  TableFilterOperationCatalogSchema,
  type FilterableDataType,
  type FqlAdapterResult,
  type FqlColumn,
  type TableFilterOperationId,
} from "../filters/fql/contracts";
import referenceJson from "./fixtures/table-filter-reference.json";

const reference = TableFilterOperationCatalogSchema.extend({
  text: z.string().min(1),
}).parse(referenceJson);
const referenceLines = reference.text.split("\n");

type FilterValue = string | number | Array<string | number>;
interface ReferenceExpectation {
  alias: string;
  types: FilterableDataType[];
  operator: OperatorType;
  value?: FilterValue;
  kind?: "scalar" | "list";
}

const SCALAR_TYPES: FilterableDataType[] = [
  "integer",
  "number",
  "date",
  "datetime",
  "time",
];
const LIST_TYPES: FilterableDataType[] = ["string", "integer", "number"];

// These expectations are independent of the generated catalog and adapter.
const EXPECTATIONS: Record<TableFilterOperationId, ReferenceExpectation> = {
  exact_text: {
    alias: "text_value",
    types: ["string"],
    operator: "equals",
    value: "chevrolet",
  },
  not_exact_text: {
    alias: "text_value",
    types: ["string"],
    operator: "does_not_equal",
    value: "chevrolet",
  },
  contains_text: {
    alias: "text_value",
    types: ["string"],
    operator: "contains",
    value: "chev",
  },
  starts_with_text: {
    alias: "text_value",
    types: ["string"],
    operator: "starts_with",
    value: "chev",
  },
  ends_with_text: {
    alias: "text_value",
    types: ["string"],
    operator: "ends_with",
    value: "let",
  },
  regex_text: {
    alias: "text_value",
    types: ["string"],
    operator: "regex",
    value: "chev.*",
  },
  contains_empty_text: {
    alias: "text_value",
    types: ["string"],
    operator: "is_not_null",
  },
  empty_text: {
    alias: "text_value",
    types: ["string"],
    operator: "is_empty",
  },
  scalar_equal: {
    alias: "quantity",
    types: SCALAR_TYPES,
    operator: "==",
    value: 4,
    kind: "scalar",
  },
  scalar_not_equal: {
    alias: "quantity",
    types: SCALAR_TYPES,
    operator: "!=",
    value: 4,
    kind: "scalar",
  },
  greater_than: {
    alias: "quantity",
    types: SCALAR_TYPES,
    operator: ">",
    value: 4,
    kind: "scalar",
  },
  greater_than_or_equal: {
    alias: "quantity",
    types: SCALAR_TYPES,
    operator: ">=",
    value: 4,
    kind: "scalar",
  },
  less_than: {
    alias: "quantity",
    types: SCALAR_TYPES,
    operator: "<",
    value: 4,
    kind: "scalar",
  },
  less_than_or_equal: {
    alias: "quantity",
    types: SCALAR_TYPES,
    operator: "<=",
    value: 4,
    kind: "scalar",
  },
  in_list: {
    alias: "text_value",
    types: LIST_TYPES,
    operator: "in",
    value: ["chevrolet", "ford"],
    kind: "list",
  },
  not_in_list: {
    alias: "text_value",
    types: LIST_TYPES,
    operator: "not_in",
    value: ["chevrolet", "ford"],
    kind: "list",
  },
  is_null: {
    alias: "text_value",
    types: FILTERABLE_DATA_TYPES,
    operator: "is_null",
  },
  is_not_null: {
    alias: "text_value",
    types: FILTERABLE_DATA_TYPES,
    operator: "is_not_null",
  },
  boolean_true: { alias: "active", types: ["boolean"], operator: "is_true" },
  boolean_false: { alias: "active", types: ["boolean"], operator: "is_false" },
};

const COLUMNS = [
  { column_id: "text_value", alias: "text_value", data_type: "string" },
  { column_id: "quantity", alias: "quantity", data_type: "integer" },
  { column_id: "active", alias: "active", data_type: "boolean" },
] satisfies FqlColumn[];

const SCALARS: Partial<
  Record<FilterableDataType, { fql: string; value: string | number }>
> = {
  integer: { fql: "4", value: 4 },
  number: { fql: '"-12.5"', value: -12.5 },
  date: { fql: '"2026-09-12"', value: "2026-09-12" },
  datetime: { fql: '"2026-09-12T14:30:00"', value: "2026-09-12T14:30:00" },
  time: { fql: '"14:30:00"', value: "14:30:00" },
};
const LISTS: Partial<
  Record<FilterableDataType, { fql: string; value: FilterValue }>
> = {
  string: { fql: '("chevrolet","ford")', value: ["chevrolet", "ford"] },
  integer: { fql: "(2,4)", value: [2, 4] },
  number: { fql: '("-12.5",0.25)', value: [-12.5, 0.25] },
};

function referenceExample(index: number): string {
  const operation = reference.operations[index];
  const line = referenceLines[index];
  const marker = ". Example: ";
  const start = line.indexOf(marker);
  const suffix = `. ${operation.meaning}`;
  expect(start).toBeGreaterThanOrEqual(0);
  expect(line.endsWith(suffix)).toBe(true);
  const query = line.slice(start + marker.length, -suffix.length);
  expect(query).toBe(operation.example);
  return query;
}

function syntaxErrors(query: string): string[] {
  const cursor = fqlLanguage.parser.parse(query).cursor();
  const errors: string[] = [];
  do {
    if (cursor.type.isError) {
      errors.push(`${cursor.from}-${cursor.to}`);
    }
  } while (cursor.next());
  return errors;
}

function expectedFilter(
  columnId: string | number,
  operator: OperatorType,
  value?: FilterValue,
): FqlAdapterResult {
  return {
    ok: true,
    filter: {
      type: "group",
      operator: "and",
      negate: false,
      children: [
        FilterConditionSchema.parse({
          type: "condition",
          column_id: columnId,
          operator,
          negate: false,
          ...(value === undefined ? {} : { value }),
        }),
      ],
    },
  };
}

function typedExample(
  query: string,
  expectation: ReferenceExpectation,
  dataType: FilterableDataType,
): { query: string; value?: FilterValue } {
  if (expectation.kind === "scalar") {
    const scalar = SCALARS[dataType];
    if (!scalar) {
      throw new Error(`No scalar example for ${dataType}`);
    }
    return { query: query.replace("4", scalar.fql), value: scalar.value };
  }
  if (expectation.kind === "list") {
    const list = LISTS[dataType];
    if (!list) {
      throw new Error(`No list example for ${dataType}`);
    }
    return {
      query: query.replace('("chevrolet","ford")', list.fql),
      value: list.value,
    };
  }
  return { query, value: expectation.value };
}

const examples = reference.operations.map((operation, index) => ({
  id: operation.id,
  index,
  expectation: EXPECTATIONS[operation.id],
}));
const typedExamples = examples.flatMap((example) =>
  example.expectation.types.map((dataType) => ({ ...example, dataType })),
);

describe("generated table-filter reference", () => {
  it("contains the complete production catalog and one line per operation", () => {
    expect({
      version: reference.version,
      operations: reference.operations,
    }).toEqual(TableFilterOperationCatalogSchema.parse(operationCatalogJson));
    expect(referenceLines).toHaveLength(reference.operations.length);
    expect(
      reference.operations.map((operation) => operation.id).toSorted(),
    ).toEqual(Object.keys(EXPECTATIONS).toSorted());
  });

  it("covers every declared operation/type/operator pair", () => {
    const actualPairs = reference.operations.flatMap((operation) =>
      operation.supported_types.map(
        (dataType) =>
          `${operation.id}:${dataType}:${operation.native_operator}`,
      ),
    );
    const expectedPairs = typedExamples.map(
      ({ id, dataType, expectation }) =>
        `${id}:${dataType}:${expectation.operator}`,
    );
    expect(actualPairs.toSorted()).toEqual(expectedPairs.toSorted());
  });

  it.each(examples)(
    "parses and adapts the rendered $id example",
    ({ index, expectation }) => {
      const query = referenceExample(index);
      expect({
        errors: syntaxErrors(query),
        result: adaptFqlFilter(query, COLUMNS),
      }).toEqual({
        errors: [],
        result: expectedFilter(
          expectation.alias,
          expectation.operator,
          expectation.value,
        ),
      });
    },
  );

  it.each(typedExamples)(
    "adapts $id for $dataType",
    ({ index, dataType, expectation }) => {
      const example = typedExample(
        referenceExample(index),
        expectation,
        dataType,
      );
      expect({
        errors: syntaxErrors(example.query),
        result: adaptFqlFilter(example.query, [
          {
            column_id: 42,
            alias: expectation.alias,
            data_type: dataType,
          },
        ]),
      }).toEqual({
        errors: [],
        result: expectedFilter(42, expectation.operator, example.value),
      });
    },
  );
});
