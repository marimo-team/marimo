/* Copyright 2024 Marimo. All rights reserved. */
const ALLOW_DEV_VERSIONS = false;

export function getPyodideVersion(marimoVersion: string) {
  return marimoVersion.includes("dev") && ALLOW_DEV_VERSIONS
    ? "dev"
    : "v0.25.0";
}

export async function importPyodide(marimoVersion: string) {
  // Vite does not like imports with dynamic urls
  return marimoVersion.includes("dev") && ALLOW_DEV_VERSIONS
    ? // @ts-expect-error typescript does not like
      await import(`https://cdn.jsdelivr.net/pyodide/dev/full/pyodide.js`)
    : // @ts-expect-error typescript does not like
      await import(`https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js`);
}
