/* Copyright 2026 Marimo. All rights reserved. */
import type { PyodideInterface } from "pyodide";

/**
 * Wrapper around pyodide.FS to add type safety.
 */
export function getFS(pyodide: PyodideInterface): PyodideInterface["FS"] {
  return pyodide.FS;
}
