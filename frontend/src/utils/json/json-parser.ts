/* Copyright 2024 Marimo. All rights reserved. */

import type { JsonString } from "./base64";

declare global {
  interface BigInt {
    toJSON(): unknown;
  }
}

// Treat BigInts as numbers
// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/JSON#using_json_numbers
BigInt.prototype.toJSON = function () {
  return JSON.rawJSON(this.toString());
};

/**
 * Parse an attribute value as JSON.
 * This also handles NaN, Infinity, and -Infinity.
 */
export function jsonParseWithSpecialChar<T = unknown>(
  value: JsonString<T> | string,
): T {
  // This regex handling is expensive and often not needed.
  // We try to parse with JSON.parse first, and if that fails, we use the regex.
  try {
    return JSON.parse(value, (_key, value) => sanitizeBigInt(value)) as T;
  } catch {
    // Do nothing
  }

  // Random unicode character that is unlikely to be used in the JSON string
  const CHAR = "◐";

  if (value == null || value === "") {
    return {} as T;
  }

  try {
    // This will properly handle NaN, Infinity, and -Infinity
    // The python json.dumps encoding will serialize to NaN, Infinity, -Infinity which is not valid JSON,
    // but we don't want to change the python encoding because NaN, Infinity, -Infinity are valuable to know.
    value = value ?? "";
    value = value.replaceAll(
      // This was iterated on with GPT. The confidence lies in the unit tests.
      /(?<=\s|^|\[|,|:)(NaN|-Infinity|Infinity)(?=(?:[^"'\\]*(\\.|'([^'\\]*\\.)*[^'\\]*'|"([^"\\]*\\.)*[^"\\]*"))*[^"']*$)/g,
      `"${CHAR}$1${CHAR}"`,
    );
    return JSON.parse(value, (_key, v) => {
      if (typeof v !== "string") {
        return sanitizeBigInt(v);
      }
      if (v === `${CHAR}NaN${CHAR}`) {
        return Number.NaN;
      }
      if (v === `${CHAR}Infinity${CHAR}`) {
        return Number.POSITIVE_INFINITY;
      }
      if (v === `${CHAR}-Infinity${CHAR}`) {
        return Number.NEGATIVE_INFINITY;
      }
      return sanitizeBigInt(v);
    }) as T;
  } catch {
    return {} as T;
  }
}

/**
 * Formats a value for TSV export, respecting user's locale for numbers
 */
function formatValueForTSV(value: unknown, locale: string): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "number" && !Number.isNaN(value)) {
    // Use toLocaleString to format numbers according to user's locale
    // This will use the appropriate decimal separator (e.g., "," in European locales)
    return value.toLocaleString(locale, {
      useGrouping: false,
      maximumFractionDigits: 20,
    });
  }
  return String(value);
}

export function jsonToTSV(json: Record<string, unknown>[], locale: string) {
  if (json.length === 0) {
    return "";
  }

  const keys = Object.keys(json[0]);
  const values = json.map((row) =>
    keys.map((key) => formatValueForTSV(row[key], locale)).join("\t"),
  );
  return `${keys.join("\t")}\n${values.join("\n")}`;
}

/** Adapted from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/BigInt#use_within_json */
function sanitizeBigInt(value: unknown): unknown {
  if (
    value !== null &&
    typeof value === "object" &&
    "$bigint" in value &&
    typeof value.$bigint === "string"
  ) {
    return BigInt(value.$bigint);
  }
  return value;
}
