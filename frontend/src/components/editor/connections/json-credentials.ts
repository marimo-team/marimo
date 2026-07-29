/* Copyright 2026 Marimo. All rights reserved. */
import { isPath, unprefixPath } from "./paths";
import { isSecret } from "./secrets";

export type JsonCredential =
  | { kind: "path"; path: string }
  | { kind: "json"; expr: string };

/**
 * Resolves a `secret_textarea` field's value — a file path, a secret
 * reference, or a raw literal — into either a path to hand to a
 * provider's path-based auth kwarg, or a `json.loads(...)` expression.
 */
export function resolveJsonCredential(
  value: string,
  printSecret: (value: string) => string,
): JsonCredential {
  if (isPath(value)) {
    return { kind: "path", path: unprefixPath(value) };
  }
  const expr = isSecret(value)
    ? `json.loads(${printSecret(value)})`
    : `json.loads("""${value}""")`;
  return { kind: "json", expr };
}

export function looksLikeJson(value: string): boolean {
  const trimmed = value.trimStart();
  return trimmed.startsWith("{") || trimmed.startsWith("[");
}

/**
 * Collapse a credential value to a single dotenv-safe line: minify JSON
 * when parseable, otherwise strip newlines.
 */
export function flattenSecretValue(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  try {
    return JSON.stringify(JSON.parse(trimmed));
  } catch {
    return value.replaceAll(/\r?\n/g, "");
  }
}

/** Escape a filesystem path for embedding in a Python double-quoted string. */
export function escapePythonString(value: string): string {
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}
