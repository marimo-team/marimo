/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Whether the current environment is Pyodide/WASM
 */
export function isWasm(): boolean {
  return document && document.querySelector("marimo-wasm") !== null;
}
