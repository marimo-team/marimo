/* Copyright 2024 Marimo. All rights reserved. */
import type { TypedString } from "@/utils/typed";

const PREFIX = "env:";

export type SecretPlaceholder = TypedString<"secret">;

export function displaySecret(value: string) {
  if (typeof value === "string" && value.startsWith(PREFIX)) {
    return value.replace(PREFIX, "$");
  }
  return value;
}

export function isSecret(value: unknown): value is SecretPlaceholder {
  if (typeof value !== "string") {
    return false;
  }
  return value.startsWith(PREFIX);
}

export function prefixSecret(value: string): SecretPlaceholder {
  return `${PREFIX}${value}` as SecretPlaceholder;
}

export function unprefixSecret(value: SecretPlaceholder): string {
  return value.replace(PREFIX, "");
}
