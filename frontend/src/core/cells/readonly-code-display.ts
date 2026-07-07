/* Copyright 2026 Marimo. All rights reserved. */

import { MarkdownParser, SQLParser } from "@marimo-team/smart-cells";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";

export interface ReadonlyCodeDisplay {
  code: string;
  language: LanguageAdapterType;
}

const markdownParser = new MarkdownParser();
const sqlParser = new SQLParser();

/**
 * Unwrap SQL and markdown cells so read-only views show inner content with the
 * correct syntax highlighting instead of the raw Python wrapper.
 */
export function getReadonlyCodeDisplay(code: string): ReadonlyCodeDisplay {
  const trimmed = code.trim();
  if (!trimmed) {
    return { code, language: "python" };
  }

  if (markdownParser.isSupported(trimmed)) {
    return {
      code: markdownParser.transformIn(trimmed).code,
      language: "markdown",
    };
  }

  if (sqlParser.isSupported(trimmed)) {
    return { code: sqlParser.transformIn(trimmed).code, language: "sql" };
  }
  return { code, language: "python" };
}
