/* Copyright 2026 Marimo. All rights reserved. */

import {
  fqlLanguage,
  parseQuery,
  type ExprNode,
  type FieldDef,
  type FilterNode,
  type FilterSchema,
  type ScalarValue,
} from "better-filter-bar";
import operationCatalogJson from "../../../../../../marimo/_server/ai/table_filter_operation_catalog.json";
import {
  FilterConditionSchema,
  type FilterConditionType,
} from "@/plugins/impl/data-frames/schema";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import {
  FqlColumnSchema,
  TableFilterOperationCatalogSchema,
  type FqlAdapterResult,
  type FqlColumn,
} from "./contracts";
import {
  convertExactList,
  convertScalarValue,
  decodeWildcardPattern,
  type ValueConversionResult,
} from "./value-conversion";

const operationCatalog =
  TableFilterOperationCatalogSchema.parse(operationCatalogJson);
const operationsById = new Map(
  operationCatalog.operations.map((operation) => [operation.id, operation]),
);

type LeafResult =
  | { ok: true; condition: FilterConditionType }
  | { ok: false; reason: string };
type Rejection = Extract<FqlAdapterResult, { ok: false }>;

function reject(reason: string): Rejection {
  return { ok: false, reason };
}

function hasSyntaxError(query: string): boolean {
  const cursor = fqlLanguage.parser.parse(query).cursor();
  do {
    if (cursor.type.isError) {
      return true;
    }
  } while (cursor.next());
  return false;
}

function toFqlField(column: FqlColumn): FieldDef {
  const base = { name: column.alias, label: String(column.column_id) };
  switch (column.data_type) {
    case "string":
      return { ...base, type: "text" };
    case "boolean":
      return { ...base, type: "boolean" };
    case "integer":
    case "number":
      return { ...base, type: "number" };
    case "date":
      return { ...base, type: "date" };
    case "datetime":
    case "time":
      return { ...base, type: "date", includeTime: true };
  }
}

function nativeOperator(
  operationId: string,
  column: FqlColumn,
): ValueConversionResult<OperatorType> {
  const operation = operationsById.get(operationId);
  if (!operation) {
    return {
      ok: false,
      reason: `The filter operation "${operationId}" is not available.`,
    };
  }
  if (!operation.supported_types.includes(column.data_type)) {
    return {
      ok: false,
      reason: `The ${column.data_type} column "${String(column.column_id)}" does not support this operation.`,
    };
  }
  return { ok: true, value: operation.native_operator };
}

function condition(
  column: FqlColumn,
  operator: OperatorType,
  value?: string | number | Array<string | number>,
): FilterConditionType {
  return FilterConditionSchema.parse({
    type: "condition",
    column_id: column.column_id,
    operator,
    ...(value === undefined ? {} : { value }),
    negate: false,
  });
}

function conditionFor(
  operationId: string,
  column: FqlColumn,
  value?: string | number | Array<string | number>,
): LeafResult {
  const operator = nativeOperator(operationId, column);
  if (!operator.ok) {
    return operator;
  }
  return {
    ok: true,
    condition: condition(column, operator.value, value),
  };
}

function isNullValue(value: ScalarValue): boolean {
  return value.value === "null";
}

function convertList(node: FilterNode, column: FqlColumn): LeafResult {
  if (node.operator !== ":" || !Array.isArray(node.value)) {
    return reject(
      `The ${column.data_type} column "${String(column.column_id)}" does not support this operation.`,
    );
  }

  const operator = nativeOperator("in_list", column);
  if (!operator.ok) {
    return operator;
  }
  const values = convertExactList(node.value, column.data_type);
  if (!values.ok) {
    return values;
  }
  return {
    ok: true,
    condition: condition(column, operator.value, values.value),
  };
}

function convertText(node: FilterNode, column: FqlColumn): LeafResult {
  if (Array.isArray(node.value)) {
    return convertList(node, column);
  }

  const value = convertScalarValue(node.value, column.data_type);
  if (!value.ok) {
    return value;
  }
  const text = String(value.value);

  if (node.operator === "=") {
    return conditionFor("exact_text", column, text);
  }
  if (node.operator === "!=") {
    return conditionFor("not_exact_text", column, text);
  }
  if (node.operator !== ":") {
    return reject(
      `The string column "${String(column.column_id)}" does not support this operation.`,
    );
  }
  if (isNullValue(node.value)) {
    return conditionFor("is_null", column);
  }
  if (text === "") {
    return conditionFor("empty_text", column);
  }
  if (text === "//") {
    return reject("A regular expression must contain a pattern.");
  }
  if (text.length >= 3 && text.startsWith("/") && text.endsWith("/")) {
    return conditionFor("regex_text", column, text.slice(1, -1));
  }

  const pattern = decodeWildcardPattern(text);
  if (!pattern.ok) {
    return pattern;
  }
  if (!pattern.value) {
    return conditionFor("exact_text", column, text);
  }

  const operationId =
    pattern.value.value === "" && pattern.value.operator === "contains"
      ? "contains_empty_text"
      : `${pattern.value.operator}_text`;
  return conditionFor(operationId, column, pattern.value.value);
}

function comparisonOperationId(
  operator: Exclude<FilterNode["operator"], ":">,
): string {
  switch (operator) {
    case "=":
      return "scalar_equal";
    case "!=":
      return "scalar_not_equal";
    case ">":
      return "greater_than";
    case ">=":
      return "greater_than_or_equal";
    case "<":
      return "less_than";
    case "<=":
      return "less_than_or_equal";
  }
}

function convertTypedScalar(node: FilterNode, column: FqlColumn): LeafResult {
  if (Array.isArray(node.value)) {
    return convertList(node, column);
  }
  if (node.operator === ":") {
    if (isNullValue(node.value)) {
      return conditionFor("is_null", column);
    }
    return reject(
      `The ${column.data_type} column "${String(column.column_id)}" does not support this operation.`,
    );
  }

  const value = convertScalarValue(node.value, column.data_type);
  if (!value.ok) {
    return value;
  }
  return conditionFor(
    comparisonOperationId(node.operator),
    column,
    value.value,
  );
}

function convertBoolean(node: FilterNode, column: FqlColumn): LeafResult {
  if (Array.isArray(node.value)) {
    return convertList(node, column);
  }
  if (node.operator !== ":") {
    return reject(
      `The boolean column "${String(column.column_id)}" does not support this operation.`,
    );
  }
  if (isNullValue(node.value)) {
    return conditionFor("is_null", column);
  }
  if (node.value.value === "true") {
    return conditionFor("boolean_true", column);
  }
  if (node.value.value === "false") {
    return conditionFor("boolean_false", column);
  }
  return reject("Expected the boolean value true or false.");
}

function convertLeaf(node: FilterNode, column: FqlColumn): LeafResult {
  switch (column.data_type) {
    case "string":
      return convertText(node, column);
    case "boolean":
      return convertBoolean(node, column);
    case "integer":
    case "number":
    case "date":
    case "datetime":
    case "time":
      return convertTypedScalar(node, column);
  }
}

function unsupportedExpression(node: ExprNode): FqlAdapterResult {
  switch (node.type) {
    case "empty":
      return reject("Enter a filter.");
    case "free_text":
      return reject("Use a column alias and an operation.");
    case "boolean":
      return reject("Boolean filter groups are not supported.");
    case "not":
      return reject("NOT filters are not supported.");
    case "filter":
      return reject("The filter condition is not supported.");
  }
}

export function adaptFqlFilter(
  query: string,
  columns: readonly FqlColumn[],
): FqlAdapterResult {
  if (query.trim() === "") {
    return reject("Enter a filter.");
  }
  if (hasSyntaxError(query)) {
    return reject("The filter has invalid FQL syntax.");
  }

  const parsedColumns = FqlColumnSchema.array().min(1).safeParse(columns);
  if (!parsedColumns.success) {
    return reject("Column metadata is invalid.");
  }

  const columnsByAlias = new Map<string, FqlColumn>();
  for (const column of parsedColumns.data) {
    const normalizedAlias = column.alias.toLowerCase();
    if (columnsByAlias.has(normalizedAlias)) {
      return reject(
        `Column aliases must be unique, ignoring case: ${column.alias}.`,
      );
    }
    columnsByAlias.set(normalizedAlias, column);
  }

  const schema: FilterSchema = {
    fields: parsedColumns.data.map(toFqlField),
    allowUnknownFields: false,
    implicitOperator: "AND",
  };
  const ast = parseQuery(query, schema);
  if (ast.type !== "filter") {
    return unsupportedExpression(ast);
  }

  const column = columnsByAlias.get(ast.field.toLowerCase());
  if (!column) {
    return reject(`Unknown column alias: ${ast.field}.`);
  }
  const converted = convertLeaf(ast, column);
  if (!converted.ok) {
    return converted;
  }
  return {
    ok: true,
    filter: {
      type: "group",
      operator: "and",
      children: [converted.condition],
      negate: false,
    },
  };
}
