/* Copyright 2024 Marimo. All rights reserved. */
import { DataFormat } from "./types";
import { isNumber } from "lodash-es";
import { typeParsers, createLoader, read, FieldTypes } from "./vega-loader";

// Augment the typeParsers to support Date
typeParsers.date = (value: string) => new Date(value).toISOString();
const previousBooleanParser = typeParsers.boolean;
const previousNumberParser = typeParsers.number;
const previousIntegerParser = typeParsers.integer;

// Custom parser to:
// - handle BigInt
// - handle inf and -inf
const customIntegerParser = (v: string) => {
  if (v === "") {
    return "";
  }
  if (v === "-inf") {
    return v;
  }
  if (v === "inf") {
    return v;
  }

  if (isNumber(Number.parseInt(v))) {
    try {
      return BigInt(v);
    } catch {
      // Floats like 2.0 are parseable as ints but not
      // as BigInt
      return previousIntegerParser(v);
    }
  } else {
    return "";
  }
};

// Custom number parser to:
// - handle inf and -inf
const customNumberParser = (v: string) => {
  if (v === "-inf") {
    return v;
  }
  if (v === "inf") {
    return v;
  }
  return previousNumberParser(v);
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

function enableBigInt() {
  typeParsers.integer = customIntegerParser;
  typeParsers.number = customNumberParser;
}

function disableBigInt() {
  typeParsers.integer = previousIntegerParser;
  typeParsers.number = previousNumberParser;
}

export const vegaLoader = createLoader();

/**
 * Load data from a URL and parse it according to the given format.
 *
 * This resolves to an array of objects, where each object represents a row.
 */
export function vegaLoadData(
  url: string,
  format: DataFormat | undefined | { type: "csv"; parse: "auto" },
  opts: {
    handleBigInt?: boolean;
    replacePeriod?: boolean;
  } = {},
): Promise<object[]> {
  const { handleBigInt = false, replacePeriod = false } = opts;

  return vegaLoader.load(url).then((csvData) => {
    // CSV data comes columnar and may have duplicate column names.
    // We need to uniquify the column names before parsing since vega-loader
    // returns an array of objects which drops duplicate keys.
    //
    // We make the column names unique by appending a number to the end of
    // each duplicate column name. If we want to preserve the original key
    // we would need to store the data in columnar format.
    if (typeof csvData === "string") {
      csvData = uniquifyColumnNames(csvData);
    }
    // Replace periods in column names with a one-dot leader.
    // Some downstream libraries use periods as a nested key separator.
    if (typeof csvData === "string" && replacePeriod) {
      csvData = replacePeriodsInColumnNames(csvData);
    }

    // We support enabling/disabling since the Table enables it
    // but Vega does not support BigInts
    if (handleBigInt) {
      enableBigInt();
    }

    // Always set parse to auto for csv data, to be able to parse dates and floats
    const results =
      format && format.type === "csv"
        ? // csv -> json
          read(csvData, {
            ...format,
            parse: (format.parse as FieldTypes) || "auto",
          })
        : read(csvData, format);

    if (handleBigInt) {
      disableBigInt();
    }

    return results;
  });
}

export function parseCsvData(csvData: string, handleBigInt = true): object[] {
  if (handleBigInt) {
    enableBigInt();
  }
  const data = read(csvData, { type: "csv", parse: "auto" });
  if (handleBigInt) {
    disableBigInt();
  }
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
