/* Copyright 2026 Marimo. All rights reserved. */

import { getResolvedMarimoConfig } from "@/core/config/config";
import type { SqlKeywordCase } from "@/core/config/config-schema";

/**
 * The user-configured keyword case for generated SQL.
 *
 * Read lazily (not cached) so setting changes apply without a reload.
 */
export function sqlKeywordCase(): SqlKeywordCase {
  return getResolvedMarimoConfig()?.runtime?.sql_keyword_case ?? "upper";
}

/**
 * Case a SQL keyword fragment per the user's configured keyword case.
 *
 * Pass keyword fragments only (e.g. "SELECT", "SELECT TOP") — never
 * identifiers, which must keep their original case.
 */
export function sqlKeyword(fragment: string): string {
  return sqlKeywordCase() === "lower"
    ? fragment.toLowerCase()
    : fragment.toUpperCase();
}
