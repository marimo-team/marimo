/* Copyright 2024 Marimo. All rights reserved. */

import { tableFromIPC } from "@uwdata/flechette";
import { isNumber } from "lodash-es";
import {
  type ByteString,
  byteStringToBinary,
  extractBase64FromDataURL,
  isDataURLString,
  typedAtob,
} from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { batchedArrowLoader, createBatchedLoader } from "./batched";
import type { DataFormat } from "./types";
import { type DataType, read, typeParsers } from "./vega-loader";

type Unsubscribe = () => void;
type Middleware = () => Unsubscribe;

// Store all the previous type parsers so we can restore them later
const previousIntegerParser = typeParsers.integer;
const previousNumberParser = typeParsers.number;
const previousDateParser = typeParsers.date;
const previousBooleanParser = typeParsers.boolean;

const BIG_INT_MIDDLEWARE: Middleware = () => {
  // Custom parser to:
  // - handle BigInt
  // - handle inf and -inf
  typeParsers.integer = (v: string) => {
    if (v === "") {
      return "";
    }
    if (v === "-inf") {
      return v;
    }
    if (v === "inf") {
      return v;
    }

    function previousIntegerParserWithoutNaN(v: string) {
      const result = previousIntegerParser(v);
      // If the result is NaN, return the original value
      if (Number.isNaN(result)) {
        return v;
      }
      return result;
    }

    const parsedInt = Number.parseInt(v);
    if (isNumber(parsedInt)) {
      const needsBigInt = Math.abs(parsedInt) > Number.MAX_SAFE_INTEGER;
      if (!needsBigInt) {
        return previousIntegerParserWithoutNaN(v);
      }
      try {
        return BigInt(v);
      } catch {
        // Floats like 2.0 are parseable as ints but not
        // as BigInt
        return previousIntegerParserWithoutNaN(v);
      }
    } else {
      return "";
    }
  };
  typeParsers.number = (v: string) => {
    if (v === "-inf") {
      return v;
    }
    if (v === "inf") {
      return v;
    }
    const result = previousNumberParser(v);
    if (Number.isNaN(result)) {
      return v;
    }
    return result;
  };

  return () => {
    typeParsers.integer = previousIntegerParser;
    typeParsers.number = previousNumberParser;
  };
};

const DATE_MIDDLEWARE: Middleware = () => {
  typeParsers.date = (value: string) => {
    if (value === "") {
      return "";
    }
    if (value == null) {
      return null;
    }
    // Only parse strings that look like ISO dates (YYYY-MM-DD with optional time)
    const isoDateRegex = /^\d{4}-\d{2}-\d{2}(T[\d.:]+(Z|[+-]\d{2}:?\d{2})?)?$/;
    if (!isoDateRegex.test(value)) {
      return value;
    }
    try {
      const date = new Date(value);
      // Ensure the date is valid by checking if it can be converted back to ISO
      if (Number.isNaN(date.getTime())) {
        return value;
      }
      return date;
    } catch {
      Logger.warn(`Failed to parse date: ${value}`);
      return value;
    }
  };
  return () => {
    typeParsers.date = previousDateParser;
  };
};

// Custom boolean parser:
//
// Pandas serializes booleans as True/False, but JSON (and vega) requires
// lowercase
const customBooleanParser = (v: string) => {
  if (v === "True") {
    return true;
  }
  if (v === "False") {
    return false;
  }
  return previousBooleanParser(v);
};

typeParsers.boolean = customBooleanParser;

export const vegaLoader = createBatchedLoader();

/**
 * Load data from a URL and parse it according to the given format.
 *
 * This resolves to an array of objects, where each object represents a row.
 */
export async function vegaLoadData<T = object>(
  url: string,
  format:
    | DataFormat
    | undefined
    | { type: "csv"; parse: "auto" }
    | { type: "arrow" },
  opts: {
    // We support enabling/disabling since the Table enables it
    // but Vega does not support BigInts
    handleBigIntAndNumberLike?: boolean;
    replacePeriod?: boolean;
  } = {},
): Promise<T[]> {
  const { handleBigIntAndNumberLike = false, replacePeriod = false } = opts;

  // Handle arrow data
  if (url.endsWith(".arrow") || format?.type === "arrow") {
    const arrow = await batchedArrowLoader(url);
    return tableFromIPC(arrow, {
      useProxy: true,
      useDate: true,
      useBigInt: handleBigIntAndNumberLike,
    }).toArray() as T[];
  }

  const middleware: Middleware[] = [DATE_MIDDLEWARE];
  if (handleBigIntAndNumberLike) {
    middleware.push(BIG_INT_MIDDLEWARE);
  }

  let unsubscribes: Unsubscribe[] = [];

  // Load the data
  try {
    let csvOrJsonData = await vegaLoader.load(url);
    if (!format) {
      // Infer by trying to parse
      if (typeof csvOrJsonData === "string") {
        try {
          JSON.parse(csvOrJsonData);
          format = { type: "json" };
        } catch {
          format = { type: "csv", parse: "auto" };
        }
      }
      if (typeof csvOrJsonData === "object") {
        format = { type: "json" };
      }
    }

    const isCsv = format?.type === "csv";
    // CSV data comes columnar and may have duplicate column names.
    // We need to uniquify the column names before parsing since vega-loader
    // returns an array of objects which drops duplicate keys.
    //
    // We make the column names unique by appending a number to the end of
    // each duplicate column name. If we want to preserve the original key
    // we would need to store the data in columnar format.
    if (isCsv && typeof csvOrJsonData === "string") {
      csvOrJsonData = uniquifyColumnNames(csvOrJsonData);
    }
    // Replace periods in column names with a one-dot leader.
    // Some downstream libraries use periods as a nested key separator.
    if (isCsv && typeof csvOrJsonData === "string" && replacePeriod) {
      csvOrJsonData = replacePeriodsInColumnNames(csvOrJsonData);
    }

    let parse = (format?.parse as Record<string, DataType>) || "auto";
    // Map some of our data types to Vega's data types
    // - time -> string
    // - datetime -> date
    if (typeof parse === "object") {
      parse = Objects.mapValues(parse, (value) => {
        if (value === "time") {
          return "string";
        }
        if (value === "datetime") {
          return "date";
        }
        return value;
      });
    }

    // Apply middleware
    unsubscribes = middleware.map((m) => m());
    // Always set parse to auto for csv data, to be able to parse dates and floats
    const results = isCsv
      ? // csv -> json
        read(csvOrJsonData, {
          ...format,
          parse: parse,
        })
      : read(csvOrJsonData, format);

    return results as T[];
  } finally {
    // Unsubscribe from middleware
    unsubscribes.forEach((u) => u());
  }
}

export function parseArrowData(data: string): Uint8Array {
  const decoded = isDataURLString(data)
    ? typedAtob(extractBase64FromDataURL(data))
    : (data as ByteString);

  return byteStringToBinary(decoded);
}

export function parseCsvData(
  csvData: string,
  handleBigIntAndNumberLike = true,
): object[] {
  const middleware: Middleware[] = [DATE_MIDDLEWARE];
  if (handleBigIntAndNumberLike) {
    middleware.push(BIG_INT_MIDDLEWARE);
  }

  // Apply middleware
  const unsubscribes = middleware.map((m) => m());

  const data = read(csvData, { type: "csv", parse: "auto" });

  // Unsubscribe from middleware
  unsubscribes.forEach((u) => u());

  return data;
}

/**
 * Make column names unique by appending a zero-width space to the end of each duplicate column name.
 */
function uniquifyColumnNames(csvData: string): string {
  if (!csvData?.includes(",")) {
    return csvData;
  }

  return mapColumnNames(csvData, (headerNames) => {
    const existingNames = new Set<string>();
    return headerNames.map((name) => {
      const uniqueName = getUniqueKey(name, existingNames);
      existingNames.add(uniqueName);
      return uniqueName;
    });
  });
}

/**
 * Replace periods in column names with a one-dot leader.
 * This is because some downstream libraries use periods as a nested key separator.
 */
function replacePeriodsInColumnNames(csvData: string): string {
  // This looks like a period but it's actually a one-dot leader
  // https://www.compart.com/en/unicode/U+2024
  const ONE_DOT_LEADER = "․";
  if (!csvData?.includes(".")) {
    return csvData;
  }

  return mapColumnNames(csvData, (headerNames) => {
    return headerNames.map((name) => name.replaceAll(".", ONE_DOT_LEADER));
  });
}

function mapColumnNames(
  csvData: string,
  fn: (names: string[]) => string[],
): string {
  const lines = csvData.split("\n");
  const header = lines[0];
  const headerNames = header.split(",");
  const newNames = fn(headerNames);
  lines[0] = newNames.join(",");
  return lines.join("\n");
}

const ZERO_WIDTH_SPACE = "\u200B";

function getUniqueKey(key: string, existingKeys: Set<string>): string {
  let result = key;
  let count = 1;
  while (existingKeys.has(result)) {
    result = `${key}${ZERO_WIDTH_SPACE.repeat(count)}`;
    count++;
  }

  return result;
}

export const exportedForTesting = {
  ZERO_WIDTH_SPACE,
  uniquifyColumnNames,
  replacePeriodsInColumnNames,
};
