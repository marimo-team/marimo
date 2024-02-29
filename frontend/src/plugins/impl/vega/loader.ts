/* Copyright 2024 Marimo. All rights reserved. */
// @ts-expect-error - no types
import { loader as createLoader, read, typeParsers } from "vega-loader";
import { DataFormat } from "./types";
import { isNumber } from "lodash-es";

// Augment the typeParsers to support Date
typeParsers.date = (value: string) => new Date(value).toISOString();
const previousIntegerParser = typeParsers.integer;
// We need to use BigInt for numbers to support large numbers
const bigIntIntegerParser = (v: string) => {
  if (v === "") {
    return "";
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

function enableBigInt() {
  typeParsers.integer = bigIntIntegerParser;
}

function disableBigInt() {
  typeParsers.integer = previousIntegerParser;
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
  handleBigInt = false,
): Promise<object[]> {
  return vegaLoader.load(url).then((csvData: string) => {
    // CSV data comes columnar and may have duplicate column names.
    // We need to uniquify the column names before parsing since vega-loader
    // returns an array of objects which drops duplicate keys.
    //
    // We make the column names unique by appending a number to the end of
    // each duplicate column name. If we want to preserve the original key
    // we would need to store the data in columnar format.
    csvData = uniquifyColumnNames(csvData);

    // We support enabling/disabling since the Table enables it
    // but Vega does not support BigInts
    if (handleBigInt) {
      enableBigInt();
    }

    // Always set parse to auto for csv data, to be able to parse dates and floats
    const results =
      format && format.type === "csv"
        ? // csv -> json
          read(csvData, { ...format, parse: "auto" })
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

export function uniquifyColumnNames(csvData: string): string {
  if (!csvData || !csvData.includes(",")) {
    return csvData;
  }

  const lines = csvData.split("\n");
  const header = lines[0];
  const headerNames = header.split(",");

  const existingNames = new Set<string>();
  const newNames = [];
  for (const name of headerNames) {
    const uniqueName = getUniqueKey(name, existingNames);
    newNames.push(uniqueName);
    existingNames.add(uniqueName);
  }

  const uniqueHeader = newNames.join(",");
  lines[0] = uniqueHeader;
  return lines.join("\n");
}

export const ZERO_WIDTH_SPACE = "\u200B";

function getUniqueKey(key: string, existingKeys: Set<string>): string {
  let result = key;
  let count = 1;
  while (existingKeys.has(result)) {
    result = `${key}${ZERO_WIDTH_SPACE.repeat(count)}`;
    count++;
  }

  return result;
}
