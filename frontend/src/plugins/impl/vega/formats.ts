/* Copyright 2024 Marimo. All rights reserved. */
import { type Table as ArrowTable, tableFromIPC } from "@uwdata/flechette";

// Adapted from https://github.com/vega/vega-loader-arrow/blob/main/src/index.js
// but this avoids bundling flechette which causes code duplication

interface IPCOptions {
  useProxy?: boolean;
}

export function arrow(data: ArrowTable): unknown[] {
  function isArrowTable(data: unknown): data is ArrowTable {
    return (
      !!(data as ArrowTable)?.schema &&
      Array.isArray((data as ArrowTable).schema.fields) &&
      typeof (data as ArrowTable).toArray === "function"
    );
  }
  return (isArrowTable(data) ? data : decodeIPC(data)).toArray();
}
arrow.responseType = "arrayBuffer";

function decodeIPC(data: ArrayBuffer, options?: IPCOptions): ArrowTable {
  return tableFromIPC(data, options ?? { useProxy: true });
}
