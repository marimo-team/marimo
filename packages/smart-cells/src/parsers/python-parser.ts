/* Copyright 2024 Marimo. All rights reserved. */

import type { FormatResult, LanguageParser, ParseResult } from "../types.js";

/**
 * Parser for Python cells (identity transformation).
 *
 * This parser simply passes through Python code unchanged.
 */
export class PythonParser implements LanguageParser<Record<string, never>> {
  readonly type = "python";
  readonly defaultCode = "";
  readonly defaultMetadata = {};

  transformIn(code: string): ParseResult<Record<string, never>> {
    return { code, offset: 0, metadata: {} };
  }

  transformOut(code: string, _metadata: Record<string, never>): FormatResult {
    return { code, offset: 0 };
  }

  isSupported(_code: string): boolean {
    return true;
  }
}
