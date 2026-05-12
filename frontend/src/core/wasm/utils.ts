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

const DUCKDB_USAGE_PATTERN =
  /(^|\n)\s*(?:import\s+[^\n#]*\bduckdb\b|from\s+duckdb\b|[^\n#]*\bduckdb\s*\.)/;

export function shouldLoadDuckDBPackages(
  code: string,
  foundPackages?: ReadonlySet<string>,
): boolean {
  return (
    code.includes("mo.sql") ||
    DUCKDB_USAGE_PATTERN.test(code) ||
    foundPackages?.has("duckdb") === true
  );
}
