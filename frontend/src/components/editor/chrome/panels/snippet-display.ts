/* Copyright 2026 Marimo. All rights reserved. */

import { SQLParser } from "@marimo-team/smart-cells";

export type SnippetLanguage = "python" | "sql";

export interface SnippetDisplay {
  language: SnippetLanguage;
  value: string;
}

const sqlParser = new SQLParser();

/**
 * Decide how a snippet's code should be shown in the panel.
 *
 * SQL cells are stored as python `mo.sql(...)`. Unwrap the inner query and
 * highlight it as SQL, matching how the cell renders once the snippet is
 * inserted. Everything else stays python.
 */
export function getSnippetDisplay(code: string): SnippetDisplay {
  if (sqlParser.isSupported(code)) {
    const { code: query } = sqlParser.transformIn(code);
    return { language: "sql", value: query };
  }
  return { language: "python", value: code };
}
