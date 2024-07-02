/* Copyright 2024 Marimo. All rights reserved. */

import { logNever } from "@/utils/assertNever";

export const QUOTE_PREFIX_KINDS = ["", "f", "r", "fr", "rf"] as const;
export type QuotePrefixKind = (typeof QUOTE_PREFIX_KINDS)[number];

// Remove the f, r, fr, rf prefixes from the quote
export function splitQuotePrefix(quote: string): [QuotePrefixKind, string] {
  // start with the longest prefix
  const prefixKindsByLength = [...QUOTE_PREFIX_KINDS].sort(
    (a, b) => b.length - a.length,
  );
  for (const prefix of prefixKindsByLength) {
    if (quote.startsWith(prefix)) {
      return [prefix, quote.slice(prefix.length)];
    }
  }
  return ["", quote];
}

export function upgradePrefixKind(
  kind: QuotePrefixKind,
  code: string,
): QuotePrefixKind {
  const containsSubstitution = code.includes("{") && code.includes("}");

  // If there is no substitution, keep the same prefix
  if (!containsSubstitution) {
    return kind;
  }

  // If there is a substitution, upgrade to an f-string
  switch (kind) {
    case "":
      return "f";
    case "r":
      return "rf";
    case "f":
    case "rf":
    case "fr":
      return kind;
    default:
      logNever(kind);
      return "f";
  }
}
