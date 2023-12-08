/* Copyright 2023 Marimo. All rights reserved. */
// @ts-expect-error - no types
import { loader as createLoader, read, typeParsers } from "vega-loader";
import { DataFormat } from "./types";

// Augment the typeParsers to support Date
typeParsers.date = (value: string) => new Date(value);

export const vegaLoader = createLoader();

export function vegaLoadData(
  url: string,
  format: DataFormat | undefined | { type: "csv"; parse: "auto" }
) {
  return vegaLoader.load(url).then((csvData: string) => {
    // csv -> json
    return read(csvData, format);
  });
}
