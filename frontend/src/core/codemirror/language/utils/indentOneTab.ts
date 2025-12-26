/* Copyright 2026 Marimo. All rights reserved. */

// Indent each line by one tab
export function indentOneTab(code: string): string {
  return code
    .split("\n")
    .map((line) => (line.trim() === "" ? line : `    ${line}`))
    .join("\n");
}
