/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Whether the current environment is Pyodide/WASM
 */
export function isWasm(): boolean {
  // Document is sometimes undefined in CI so we check to reduce flakiness
  return (
    typeof document !== "undefined" &&
    document.querySelector("marimo-wasm") !== null
  );
}
