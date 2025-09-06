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
    const parsed = JSON.parse(value) as T;
    // Convert string-encoded large integers to BigInt for proper display
    return convertLargeIntegersToBigInt(parsed);
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
    const parsed = JSON.parse(value, (key, v) => {
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
    // Convert string-encoded large integers to BigInt for proper display
    return convertLargeIntegersToBigInt(parsed);
  } catch {
    return {} as T;
  }
}

/**
 * Recursively converts string-encoded large integers to BigInt for proper display.
 * This handles integers that are outside JavaScript's safe integer range
 * and were serialized as strings by the backend to prevent precision loss.
 */
function convertLargeIntegersToBigInt<T>(obj: T): T {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(convertLargeIntegersToBigInt) as T;
  }

  if (typeof obj === "object") {
    const result = {} as T;
    for (const [key, value] of Object.entries(obj)) {
      (result as Record<string, unknown>)[key] = convertLargeIntegersToBigInt(value);
    }
    return result;
  }

  if (typeof obj === "string" && // Check if the string represents a large integer
    isLargeIntegerString(obj)) {
      try {
        return BigInt(obj) as T;
      } catch {
        // If BigInt conversion fails, return the original string
        return obj;
      }
    }

  return obj;
}

/**
 * Checks if a string represents a large integer that should be converted to BigInt.
 * Only converts integers that are outside JavaScript's safe integer range.
 */
function isLargeIntegerString(str: string): boolean {
  // Must be a string representing an integer (no decimals, no scientific notation)
  if (!/^-?\d+$/.test(str)) {
    return false;
  }

  // Parse as number to check if it's outside safe integer range
  const num = Number(str);
  
  // If it's NaN or not finite, don't convert
  if (!Number.isFinite(num)) {
    return false;
  }

  // Only convert if it's outside the safe integer range
  return Math.abs(num) > Number.MAX_SAFE_INTEGER;
}

export function jsonToTSV(json: Array<Record<string, unknown>>) {
  if (json.length === 0) {
    return "";
  }

  const keys = Object.keys(json[0]);
  const values = json.map((row) => keys.map((key) => row[key]).join("\t"));
  return `${keys.join("\t")}\n${values.join("\n")}`;
}
