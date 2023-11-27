/* Copyright 2023 Marimo. All rights reserved. */
// @ts-expect-error - no types
import { loader as createLoader, read } from "vega-loader";
import { DataFormat } from "./types";

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
