/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Whether the current environment is Pyodide/WASM
 */
export function isWasm() {
  return document.querySelector("marimo-wasm") !== null;
}
