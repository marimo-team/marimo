/* Copyright 2024 Marimo. All rights reserved. */

import dedent from "string-dedent";

/**
 * Safely dedent a string, handling cases where dedent might fail.
 *
 * The dedent library expects the first and last lines to be empty or contain
 * only whitespace, so we pad with newlines before dedenting.
 *
 * @param code - The code to dedent
 * @returns The dedented code, or the original code if dedenting fails
 */
export function safeDedent(code: string): string {
  try {
    // Dedent expects the first and last line to be empty / contain only whitespace,
    // so we pad with \n
    return dedent(`\n${code}\n`).trim();
  } catch {
    return code;
  }
}
