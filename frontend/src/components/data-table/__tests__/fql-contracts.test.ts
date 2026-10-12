/* Copyright 2026 Marimo. All rights reserved. */

import { fqlLanguage } from "better-filter-bar";
import { describe, expect, it } from "vitest";
import conformanceCasesJson from "../../../../../marimo/_server/ai/table_filter_conformance_cases.json";
import operationCatalogJson from "../../../../../marimo/_server/ai/table_filter_operation_catalog.json";
import {
  FILTERABLE_DATA_TYPES,
  TableFilterConformanceSuiteSchema,
  TableFilterOperationCatalogSchema,
  type FilterableDataType,
} from "../filters/fql/contracts";

const operationCatalog =
  TableFilterOperationCatalogSchema.parse(operationCatalogJson);
const conformanceSuite =
  TableFilterConformanceSuiteSchema.parse(conformanceCasesJson);

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

describe("FQL shared contracts", () => {
  it("validates the operation catalog and conformance cases", () => {
    expect(operationCatalog.version).toBe(1);
    expect(conformanceSuite.version).toBe(1);
  });

  it("preserves the shared refusal cases", () => {
    expect(conformanceSuite.refusals).toEqual([
      {
        id: "missing_column",
        request: "Show vehicles with horsepower above 200.",
        explanation: "The table has no horsepower column.",
      },
      {
        id: "unavailable_statistic",
        request: "Show vehicles with a price above the median.",
        explanation:
          "The median price is unavailable. Provide a concrete price threshold instead.",
      },
    ]);
  });

  it("rejects a refusal without an explanation", () => {
    expect(
      TableFilterConformanceSuiteSchema.safeParse({
        ...conformanceCasesJson,
        refusals: [
          { id: "missing_column", request: "Filter an absent column." },
        ],
      }).success,
    ).toBe(false);
  });

  it("uses unique operation IDs, aliases, case IDs, and row IDs", () => {
    const operationIds = operationCatalog.operations.map(
      (operation) => operation.id,
    );
    const aliases = conformanceSuite.table.columns.map(
      (column) => column.alias,
    );
    const caseIds = [
      ...conformanceSuite.cases.map((testCase) => testCase.id),
      ...conformanceSuite.refusals.map((testCase) => testCase.id),
    ];
    const rowIds = conformanceSuite.table.rows.map((row) => row.row_id);

    expect(new Set(operationIds).size).toBe(operationIds.length);
    expect(new Set(aliases).size).toBe(aliases.length);
    expect(new Set(caseIds).size).toBe(caseIds.length);
    expect(new Set(rowIds).size).toBe(rowIds.length);
  });

  it("covers every filterable data type with complete rows", () => {
    const dataTypes = conformanceSuite.table.columns.map(
      (column) => column.data_type,
    );
    const columnIds = conformanceSuite.table.columns.map((column) =>
      String(column.column_id),
    );

    expect(new Set(dataTypes)).toEqual(new Set(FILTERABLE_DATA_TYPES));
    for (const row of conformanceSuite.table.rows) {
      expect(Object.keys(row.values).toSorted()).toEqual(columnIds.toSorted());
    }
  });

  it("covers every supported native operator for each data type", () => {
    const expectedOperators: Record<FilterableDataType, Set<string>> = {
      string: new Set([
        "equals",
        "does_not_equal",
        "contains",
        "regex",
        "starts_with",
        "ends_with",
        "in",
        "not_in",
        "is_empty",
        "is_null",
        "is_not_null",
      ]),
      boolean: new Set(["is_true", "is_false", "is_null", "is_not_null"]),
      integer: new Set([
        "==",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "in",
        "not_in",
        "is_null",
        "is_not_null",
      ]),
      number: new Set([
        "==",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "in",
        "not_in",
        "is_null",
        "is_not_null",
      ]),
      date: new Set([
        "==",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "is_null",
        "is_not_null",
      ]),
      datetime: new Set([
        "==",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "is_null",
        "is_not_null",
      ]),
      time: new Set([
        "==",
        "!=",
        ">",
        ">=",
        "<",
        "<=",
        "is_null",
        "is_not_null",
      ]),
    };

    for (const dataType of FILTERABLE_DATA_TYPES) {
      const actualOperators = new Set(
        operationCatalog.operations
          .filter((operation) => operation.supported_types.includes(dataType))
          .map((operation) => operation.native_operator),
      );
      expect(actualOperators).toEqual(expectedOperators[dataType]);
    }
  });

  it("references only declared operations", () => {
    const operationIds = new Set(
      operationCatalog.operations.map((operation) => operation.id),
    );

    for (const testCase of conformanceSuite.cases) {
      expect(
        testCase.operation_ids.every((operationId) =>
          operationIds.has(operationId),
        ),
      ).toBe(true);
    }
  });

  it("parses every FQL example without syntax recovery", () => {
    for (const operation of operationCatalog.operations) {
      expect({
        id: operation.id,
        errors: syntaxErrors(operation.example),
      }).toEqual({ id: operation.id, errors: [] });
    }
    for (const testCase of conformanceSuite.cases) {
      expect({ id: testCase.id, errors: syntaxErrors(testCase.fql) }).toEqual({
        id: testCase.id,
        errors: [],
      });
    }
  });
});
