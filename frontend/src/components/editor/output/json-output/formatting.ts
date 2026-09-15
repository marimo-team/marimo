/* Copyright 2026 Marimo. All rights reserved. */
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";

export function splitLeaf(leaf: string): [string, string | undefined] {
  const index = leaf.indexOf(":");
  return index < 0
    ? [leaf, undefined]
    : [leaf.slice(index + 1), leaf.slice(0, index)];
}

function formatFloat(value: string): string {
  switch (value.toLowerCase()) {
    case "nan":
      return "float('nan')";
    case "inf":
    case "infinity":
      return "float('inf')";
    case "-inf":
    case "-infinity":
      return "-float('inf')";
    default:
      return value;
  }
}

function formatCollection(
  payload: string,
  kind: "tuple" | "set" | "frozenset",
): string {
  const items = jsonParseWithSpecialChar<unknown>(payload);
  // Older servers sent Python literals instead of JSON lists.
  if (!Array.isArray(items)) {
    return payload;
  }
  const inner = items.map((item) => formatPython(item, true)).join(", ");
  switch (kind) {
    case "tuple":
      return `(${inner}${items.length === 1 ? "," : ""})`;
    case "set":
      return items.length ? `{${inner}}` : "set()";
    case "frozenset":
      return items.length ? `frozenset({${inner}})` : "frozenset()";
  }
}

export const formatTuplePayload = (payload: string) =>
  formatCollection(payload, "tuple");
export const formatSetPayload = (payload: string) =>
  formatCollection(payload, "set");
export const formatFrozensetPayload = (payload: string) =>
  formatCollection(payload, "frozenset");

// Matches the key encoding in marimo/_output/formatters/structures.py.
export function decodePythonKey(
  key: unknown,
): { text: string; quoted: boolean } | undefined {
  if (typeof key !== "string") {
    return undefined;
  }
  const [payload, mime] = splitLeaf(key);
  switch (mime) {
    case "text/plain+str":
      return { text: payload, quoted: true };
    case "text/plain+int":
    case "text/plain+float":
      return { text: payload, quoted: false };
    case "text/plain+bool":
      return { text: payload === "True" ? "True" : "False", quoted: false };
    case "text/plain+none":
      return { text: "None", quoted: false };
    case "text/plain+tuple":
      return { text: formatTuplePayload(payload), quoted: false };
    case "text/plain+frozenset":
      return { text: formatFrozensetPayload(payload), quoted: false };
    default:
      return undefined;
  }
}

function formatKey(key: string): string {
  const decoded = decodePythonKey(key);
  if (!decoded) {
    return JSON.stringify(key);
  }
  if (decoded.quoted) {
    return JSON.stringify(decoded.text);
  }
  return key.startsWith("text/plain+float:")
    ? formatFloat(decoded.text)
    : decoded.text;
}

function formatString(value: string): string {
  const [payload, mime] = splitLeaf(value);
  switch (mime) {
    case "text/plain+float":
      return formatFloat(payload);
    case "text/plain+bigint":
      return BigInt(payload).toString();
    case "text/plain+tuple":
      return formatTuplePayload(payload);
    case "text/plain+set":
      return formatSetPayload(payload);
    case "text/plain+frozenset":
      return formatFrozensetPayload(payload);
    case "text/plain":
    case "text/html":
    case "text/markdown":
      return JSON.stringify(payload);
    default:
      return JSON.stringify(
        mime && /^(image|video|application)\//.test(mime) ? payload : value,
      );
  }
}

function formatPython(value: unknown, compact = false): string {
  const ancestors = new WeakSet<object>();
  function format(node: unknown, depth: number): string {
    if (node == null) {
      return "None";
    }
    switch (typeof node) {
      case "string":
        return compact ? JSON.stringify(node) : formatString(node);
      case "boolean":
        return node ? "True" : "False";
      case "number":
        return formatFloat(String(node));
      case "bigint":
        return node.toString();
      case "object":
        if (ancestors.has(node)) {
          throw new TypeError("Cannot copy circular data");
        }
        ancestors.add(node);
        try {
          const array = Array.isArray(node);
          const entries = array
            ? Array.from(node, (item) => format(item, depth + 1))
            : Object.entries(node).map(
                ([key, item]) =>
                  `${compact ? JSON.stringify(key) : formatKey(key)}: ${format(item, depth + 1)}`,
              );
          const [open, close] = array ? ["[", "]"] : ["{", "}"];
          if (entries.length === 0) {
            return open + close;
          }
          if (compact) {
            return `${open}${entries.join(", ")}${close}`;
          }
          const indent = "  ".repeat(depth);
          return `${open}\n${indent}  ${entries.join(`,\n${indent}  `)}\n${indent}${close}`;
        } finally {
          ancestors.delete(node);
        }

      default:
        return "None";
    }
  }
  return format(value, 0);
}

export function getCopyValue(value: unknown): string {
  return formatPython(value);
}
