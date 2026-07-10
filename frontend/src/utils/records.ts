/* Copyright 2026 Marimo. All rights reserved. */

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function hasFunctionProperty(
  record: Record<string, unknown>,
  key: string,
): boolean {
  return typeof record[key] === "function";
}
