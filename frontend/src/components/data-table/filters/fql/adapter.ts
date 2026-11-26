/* Copyright 2026 Marimo. All rights reserved. */

import {
  fqlLanguage,
  parseQuery,
  type BooleanNode,
  type ExprNode,
  type FilterNode,
  type FilterSchema,
  type NotNode,
  type ScalarValue,
} from "better-filter-bar";
import operationCatalogJson from "../../../../../../marimo/_server/ai/table_filter_operation_catalog.json";
import {
  FilterConditionSchema,
  type FilterConditionType,
  type FilterGroupType,
} from "@/plugins/impl/data-frames/schema";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { assertNever } from "@/utils/assertNever";
import {
  FqlColumnSchema,
  TableFilterOperationCatalogSchema,
  type FqlAdapterResult,
  type FqlColumn,
  type TableFilterOperationId,
} from "./contracts";
import {
  convertExactList,
  convertScalarValue,
  decodeWildcardEscapes,
  decodeWildcardPattern,
  type ValueConversionResult,
  type WildcardPattern,
} from "./value-conversion";

const operationCatalog =
  TableFilterOperationCatalogSchema.parse(operationCatalogJson);
const operationsById = new Map(
  operationCatalog.operations.map((operation) => [operation.id, operation]),
);

type Rejection = Extract<FqlAdapterResult, { ok: false }>;
type NativeFilterNode = FilterConditionType | FilterGroupType;
type ConversionResult<T extends NativeFilterNode> =
  | { ok: true; node: T }
  | Rejection;
type ConditionResult = ConversionResult<FilterConditionType>;
type ExpressionResult = ConversionResult<NativeFilterNode>;

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

function nativeOperator(
  operationId: TableFilterOperationId,
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
    return unsupportedOperation(column);
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
  operationId: TableFilterOperationId,
  column: FqlColumn,
  value?: string | number | Array<string | number>,
): ConditionResult {
  const operator = nativeOperator(operationId, column);
  if (!operator.ok) {
    return operator;
  }
  return {
    ok: true,
    node: condition(column, operator.value, value),
  };
}

function isNullValue(value: ScalarValue): boolean {
  // The parser normalizes bare and quoted strings to the same scalar value,
  // so the colon form reserves both `null` and `"null"` for null checks.
  return value.value === "null";
}

function validateRegex(pattern: string): Rejection | undefined {
  try {
    RegExp(pattern);
    return undefined;
  } catch {
    return reject("Expected a valid regular expression.");
  }
}

function unsupportedOperation(column: FqlColumn): Rejection {
  return reject(
    `The ${column.data_type} column "${String(column.column_id)}" does not support this operation.`,
  );
}

function convertList(
  fqlOperator: FilterNode["operator"],
  values: ScalarValue[],
  column: FqlColumn,
  operationId: "in_list" | "not_in_list" = "in_list",
): ConditionResult {
  if (fqlOperator !== ":") {
    return unsupportedOperation(column);
  }

  const operatorResult = nativeOperator(operationId, column);
  if (!operatorResult.ok) {
    return operatorResult;
  }
  const convertedValues = convertExactList(values, column.data_type);
  if (!convertedValues.ok) {
    return convertedValues;
  }
  return {
    ok: true,
    node: condition(column, operatorResult.value, convertedValues.value),
  };
}

const WILDCARD_OPERATION_IDS: Record<
  WildcardPattern["operator"],
  TableFilterOperationId
> = {
  contains: "contains_text",
  starts_with: "starts_with_text",
  ends_with: "ends_with_text",
};

const COMPARISON_OPERATION_IDS: Record<
  Exclude<FilterNode["operator"], ":">,
  TableFilterOperationId
> = {
  "=": "scalar_equal",
  "!=": "scalar_not_equal",
  ">": "greater_than",
  ">=": "greater_than_or_equal",
  "<": "less_than",
  "<=": "less_than_or_equal",
};

function convertText(
  operator: FilterNode["operator"],
  scalar: ScalarValue,
  column: FqlColumn,
): ConditionResult {
  const value = convertScalarValue(scalar, column.data_type);
  if (!value.ok) {
    return value;
  }
  const text = String(value.value);

  if (operator === "=") {
    return conditionFor("exact_text", column, text);
  }
  if (operator === "!=") {
    return conditionFor("not_exact_text", column, text);
  }
  if (operator !== ":") {
    return unsupportedOperation(column);
  }
  if (isNullValue(scalar)) {
    return conditionFor("is_null", column);
  }
  if (text === "") {
    return conditionFor("empty_text", column);
  }
  if (text === "//") {
    return reject("A regular expression must contain a pattern.");
  }
  if (text.length >= 3 && text.startsWith("/") && text.endsWith("/")) {
    const regex = text.slice(1, -1);
    const invalidRegex = validateRegex(regex);
    return invalidRegex ?? conditionFor("regex_text", column, regex);
  }

  const pattern = decodeWildcardPattern(text);
  if (!pattern.ok) {
    return pattern;
  }
  if (!pattern.value) {
    return conditionFor("exact_text", column, decodeWildcardEscapes(text));
  }

  if (pattern.value.value === "" && pattern.value.operator === "contains") {
    return conditionFor("contains_empty_text", column);
  }
  const operationId = WILDCARD_OPERATION_IDS[pattern.value.operator];
  return conditionFor(operationId, column, pattern.value.value);
}

function convertTypedScalar(
  operator: FilterNode["operator"],
  scalar: ScalarValue,
  column: FqlColumn,
): ConditionResult {
  if (operator === ":") {
    if (isNullValue(scalar)) {
      return conditionFor("is_null", column);
    }
    return unsupportedOperation(column);
  }

  const value = convertScalarValue(scalar, column.data_type);
  if (!value.ok) {
    return value;
  }
  return conditionFor(COMPARISON_OPERATION_IDS[operator], column, value.value);
}

function convertBoolean(
  operator: FilterNode["operator"],
  scalar: ScalarValue,
  column: FqlColumn,
): ConditionResult {
  if (operator !== ":") {
    return unsupportedOperation(column);
  }
  if (isNullValue(scalar)) {
    return conditionFor("is_null", column);
  }
  if (scalar.value === "true") {
    return conditionFor("boolean_true", column);
  }
  if (scalar.value === "false") {
    return conditionFor("boolean_false", column);
  }
  return reject("Expected the boolean value true or false.");
}

function convertLeaf(node: FilterNode, column: FqlColumn): ConditionResult {
  if (Array.isArray(node.value)) {
    return convertList(node.operator, node.value, column);
  }

  switch (column.data_type) {
    case "string":
      return convertText(node.operator, node.value, column);
    case "boolean":
      return convertBoolean(node.operator, node.value, column);
    case "integer":
    case "number":
    case "date":
    case "datetime":
    case "time":
      return convertTypedScalar(node.operator, node.value, column);
    default:
      return assertNever(column.data_type);
  }
}

function columnFor(
  node: FilterNode,
  columnsByAlias: ReadonlyMap<string, FqlColumn>,
): ValueConversionResult<FqlColumn> {
  const column = columnsByAlias.get(node.field.toLowerCase());
  return column
    ? { ok: true, value: column }
    : reject(`Unknown column alias: ${node.field}.`);
}

function convertFilter(
  node: FilterNode,
  columnsByAlias: ReadonlyMap<string, FqlColumn>,
): ExpressionResult {
  const column = columnFor(node, columnsByAlias);
  if (!column.ok) {
    return column;
  }
  return convertLeaf(node, column.value);
}

function convertNot(
  node: NotNode,
  columnsByAlias: ReadonlyMap<string, FqlColumn>,
): ExpressionResult {
  if (node.operand.type !== "filter") {
    return reject("NOT can only be applied to a list or null filter.");
  }

  const column = columnFor(node.operand, columnsByAlias);
  if (!column.ok) {
    return column;
  }
  if (Array.isArray(node.operand.value)) {
    return convertList(
      node.operand.operator,
      node.operand.value,
      column.value,
      "not_in_list",
    );
  }
  if (node.operand.operator === ":" && isNullValue(node.operand.value)) {
    return conditionFor("is_not_null", column.value);
  }
  return reject("NOT can only be applied to a list or null filter.");
}

function appendChild(
  children: FilterGroupType["children"],
  node: NativeFilterNode,
  operator: FilterGroupType["operator"],
): void {
  if (node.type === "group" && node.operator === operator && !node.negate) {
    children.push(...node.children);
    return;
  }
  children.push(node);
}

function convertBooleanExpression(
  node: BooleanNode,
  columnsByAlias: ReadonlyMap<string, FqlColumn>,
): ExpressionResult {
  const left = convertExpression(node.left, columnsByAlias);
  if (!left.ok) {
    return left;
  }
  const right = convertExpression(node.right, columnsByAlias);
  if (!right.ok) {
    return right;
  }

  const operator = node.operator === "AND" ? "and" : "or";
  const children: FilterGroupType["children"] = [];
  appendChild(children, left.node, operator);
  appendChild(children, right.node, operator);
  return {
    ok: true,
    node: { type: "group", operator, children, negate: false },
  };
}

function convertExpression(
  node: ExprNode,
  columnsByAlias: ReadonlyMap<string, FqlColumn>,
): ExpressionResult {
  switch (node.type) {
    case "empty":
      return reject("Enter a filter.");
    case "free_text":
      return reject("Use a column alias and an operation.");
    case "boolean":
      return convertBooleanExpression(node, columnsByAlias);
    case "not":
      return convertNot(node, columnsByAlias);
    case "filter":
      return convertFilter(node, columnsByAlias);
    default:
      return assertNever(node);
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
    fields: parsedColumns.data.map((column) => ({
      name: column.alias,
      label: String(column.column_id),
      type: "text",
    })),
    allowUnknownFields: false,
    implicitOperator: "AND",
  };
  const ast = parseQuery(query, schema);
  const converted = convertExpression(ast, columnsByAlias);
  if (!converted.ok) {
    return converted;
  }
  return {
    ok: true,
    filter:
      converted.node.type === "group"
        ? converted.node
        : {
            type: "group",
            operator: "and",
            children: [converted.node],
            negate: false,
          },
  };
}
