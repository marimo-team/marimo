/* Copyright 2024 Marimo. All rights reserved. */

import type { JsonString } from "./base64";

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
    return JSON.parse(value) as T;
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
    return JSON.parse(value, (key, v) => {
      if (typeof v !== "string") {
        return v;
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
      return v;
    }) as T;
  } catch {
    return {} as T;
  }
}

export function jsonToTSV(json: Array<Record<string, unknown>>) {
  if (json.length === 0) {
    return "";
  }

  const keys = Object.keys(json[0]);
  const values = json.map((row) => keys.map((key) => row[key]).join("\t"));
  return `${keys.join("\t")}\n${values.join("\n")}`;
}
