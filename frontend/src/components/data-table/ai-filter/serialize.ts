/* Copyright 2026 Marimo. All rights reserved. */

import type { ExprNode, FilterNode, ScalarValue } from "better-filter-bar";
import { scalarToString, scalarToValue } from "better-filter-bar";
import type { DataType } from "@/core/kernel/messages";
import type {
  FilterConditionType,
  FilterGroupType,
} from "@/plugins/impl/data-frames/schema";
import type { ColumnId } from "@/plugins/impl/data-frames/types";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import type { FieldTypesWithExternalType } from "../types";

export interface SerializedFilter {
  filters: FilterGroupType | null;
  /** Free-text tokens with no column to bind to; forwarded to the `query` param. */
  query: string;
}

type ConditionOrGroup = FilterConditionType | FilterGroupType;

interface Converted {
  node: ConditionOrGroup | null;
  freeText: string[];
}

/**
 * Serialize a better-filter-bar AST into marimo's native filter format. Pure —
 * resolve relative dates on the AST before calling so tests stay stable.
 */
export function filterBarAstToMarimo(
  ast: ExprNode,
  fieldTypes: FieldTypesWithExternalType | null | undefined,
): SerializedFilter {
  const { node, freeText } = convert(ast, fieldTypes ?? []);
  const query = freeText.join(" ").trim();

  if (node == null) {
    return { filters: null, query };
  }
  if (node.type === "group") {
    return { filters: node, query };
  }
  // A bare condition is wrapped in an AND group — the search RPC expects a group.
  return { filters: wrapGroup("and", [node]), query };
}

/**
 * Combine the existing column-derived filter group with an AI-generated group.
 * Empty groups are dropped; otherwise the two are AND-ed together.
 */
export function mergeFilterGroups(
  base: FilterGroupType,
  extra: FilterGroupType | null | undefined,
): FilterGroupType {
  if (extra == null || extra.children.length === 0) {
    return base;
  }
  if (base.children.length === 0) {
    return extra;
  }
  return wrapGroup("and", [base, extra]);
}

// --- internals --------------------------------------------------------------

function convert(
  node: ExprNode,
  fieldTypes: FieldTypesWithExternalType,
): Converted {
  switch (node.type) {
    case "empty":
      return { node: null, freeText: [] };
    case "free_text":
      return { node: null, freeText: [node.value] };
    case "filter":
      return { node: convertFilter(node, fieldTypes), freeText: [] };
    case "not": {
      const inner = convert(node.operand, fieldTypes);
      return {
        node: inner.node == null ? null : negate(inner.node),
        freeText: inner.freeText,
      };
    }
    case "boolean": {
      const left = convert(node.left, fieldTypes);
      const right = convert(node.right, fieldTypes);
      const freeText = [...left.freeText, ...right.freeText];
      const operator = node.operator === "OR" ? "or" : "and";
      const children = [left.node, right.node].filter(
        (n): n is ConditionOrGroup => n != null,
      );
      if (children.length === 0) {
        return { node: null, freeText };
      }
      if (children.length === 1) {
        return { node: children[0], freeText };
      }
      return {
        node: wrapGroup(operator, flatten(operator, children)),
        freeText,
      };
    }
  }
}

function convertFilter(
  node: FilterNode,
  fieldTypes: FieldTypesWithExternalType,
): FilterConditionType {
  const columnId = node.field as ColumnId;
  const dataType = columnDataType(fieldTypes, node.field);

  // Multi-value: `status:(open,closed)` → `in`
  if (Array.isArray(node.value)) {
    return {
      type: "condition",
      column_id: columnId,
      operator: "in",
      value: node.value.map((v) => scalarToValue(v)),
      negate: false,
    };
  }

  const { operator, value } = mapOperator({
    fqlOperator: node.operator,
    dataType,
    value: node.value,
  });
  const condition: FilterConditionType = {
    type: "condition",
    column_id: columnId,
    operator,
    negate: false,
  };
  if (value !== undefined) {
    condition.value = value;
  }
  return condition;
}

function mapOperator(opts: {
  fqlOperator: FilterNode["operator"];
  dataType: DataType | undefined;
  value: ScalarValue;
}): { operator: OperatorType; value?: unknown } {
  const { fqlOperator, dataType, value } = opts;
  // Comparison operators map straight across (only produced for number/date).
  switch (fqlOperator) {
    case "!=":
    case ">":
    case ">=":
    case "<":
    case "<=":
      return { operator: fqlOperator, value: scalarToValue(value) };
    case "=":
    case ":":
      break;
  }

  // `:` / `=` resolve by column type.
  switch (dataType) {
    case "boolean":
      return { operator: isTruthy(value) ? "is_true" : "is_false" };
    case "integer":
    case "number":
    case "date":
    case "datetime":
    case "time":
      return { operator: "==", value: scalarToValue(value) };
    default:
      // text / unknown columns: `=` is exact, `:` is a contains match.
      return {
        operator: fqlOperator === "=" ? "equals" : "contains",
        value: scalarToString(value),
      };
  }
}

function isTruthy(value: ScalarValue): boolean {
  if (value.kind === "number") {
    return value.value !== 0;
  }
  const normalized = String(value.value).toLowerCase();
  return normalized === "true" || normalized === "1" || normalized === "yes";
}

function columnDataType(
  fieldTypes: FieldTypesWithExternalType,
  column: string,
): DataType | undefined {
  return fieldTypes.find(([name]) => name === column)?.[1][0];
}

function negate(node: ConditionOrGroup): ConditionOrGroup {
  return { ...node, negate: !node.negate };
}

/** Collapse nested same-operator, non-negated groups into their parent. */
function flatten(
  operator: "and" | "or",
  children: ConditionOrGroup[],
): ConditionOrGroup[] {
  return children.flatMap((child) =>
    child.type === "group" && child.operator === operator && !child.negate
      ? child.children
      : [child],
  );
}

function wrapGroup(
  operator: "and" | "or",
  children: ConditionOrGroup[],
): FilterGroupType {
  return { type: "group", operator, children, negate: false };
}
