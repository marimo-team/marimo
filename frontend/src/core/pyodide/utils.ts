/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Whether the current environment is Pyodide/WASM
 */
export function isPyodide() {
  return document.querySelector("marimo-wasm") !== null;
}
