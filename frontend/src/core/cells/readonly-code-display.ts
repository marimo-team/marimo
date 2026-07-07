/* Copyright 2026 Marimo. All rights reserved. */

import { SQLParser } from "@marimo-team/smart-cells";

export type ReadonlyCodeLanguage = "python" | "sql";

export interface ReadonlyCodeDisplay {
  code: string;
  language: ReadonlyCodeLanguage;
}

const sqlParser = new SQLParser();

/**
 * Unwrap SQL cells to their inner query so read-only views highlight them as
 * SQL instead of showing the raw `mo.sql(...)` wrapper.
 */
export function getReadonlyCodeDisplay(code: string): ReadonlyCodeDisplay {
  const trimmed = code.trim();
  if (sqlParser.isSupported(trimmed)) {
    return { code: sqlParser.transformIn(trimmed).code, language: "sql" };
  }
  return { code, language: "python" };
}
