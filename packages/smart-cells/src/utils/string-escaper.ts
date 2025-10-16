/* Copyright 2024 Marimo. All rights reserved. */

import type { QuoteType } from "../types.js";

/**
 * Escape quotes in a string for safe embedding in Python code.
 *
 * @param code - The code to escape
 * @param quoteType - The quote type to escape
 * @returns The escaped code
 */
export function escapeQuotes(code: string, quoteType: QuoteType): string {
  if (quoteType === '"""') {
    return code.replaceAll('"""', String.raw`\"""`);
  }
  if (quoteType === "'''") {
    return code.replaceAll("'''", String.raw`\'\'\'`);
  }
  if (quoteType === '"') {
    return code.replaceAll('"', String.raw`\"`);
  }
  if (quoteType === "'") {
    return code.replaceAll("'", String.raw`\'`);
  }
  return code;
}

/**
 * Unescape quotes in a string extracted from Python code.
 *
 * @param code - The code with escaped quotes
 * @param quoteType - The quote type that was escaped
 * @returns The unescaped code
 */
export function unescapeQuotes(code: string, quoteType: QuoteType): string {
  return code.replaceAll(`\\${quoteType}`, quoteType);
}
