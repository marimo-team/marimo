/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Quote one argument for a POSIX shell command.
 *
 * Mirrors Python's `shlex.quote` so copied commands cannot interpret argument
 * contents as shell syntax.
 */
export function shellQuote(value: string): string {
  if (value === "") {
    return "''";
  }
  if (/^[\w@%+=:,./-]+$/.test(value)) {
    return value;
  }
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}
