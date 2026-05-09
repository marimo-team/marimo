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

const DUCKDB_IMPORT = /^(import\s+duckdb\b|from\s+duckdb\s+import\b)/;
const DUCKDB_USAGE = /(^|[^"'#])\bduckdb\s*\./;

function hasDuckDBImportOrUsage(code: string): boolean {
  return code.split("\n").some((line) => {
    const trimmed = line.trimStart();
    if (trimmed.startsWith("#")) {
      return false;
    }
    if (DUCKDB_IMPORT.test(trimmed)) {
      return true;
    }
    return DUCKDB_USAGE.test(line.split("#")[0]);
  });
}

export function shouldLoadDuckDBPackages(
  code: string,
  foundPackages?: ReadonlySet<string>,
): boolean {
  return (
    code.includes("mo.sql") ||
    foundPackages?.has("duckdb") === true ||
    hasDuckDBImportOrUsage(code)
  );
}
