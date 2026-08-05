/* Copyright 2026 Marimo. All rights reserved. */
import type { TypedString } from "@/utils/typed";

const PREFIX = "path:";

export type PathPlaceholder = TypedString<"path">;

export function isPath(value: unknown): value is PathPlaceholder {
  if (typeof value !== "string") {
    return false;
  }
  return value.startsWith(PREFIX);
}

export function prefixPath(value: string): PathPlaceholder {
  return `${PREFIX}${value}` as PathPlaceholder;
}

export function unprefixPath(value: PathPlaceholder): string {
  return value.slice(PREFIX.length);
}
