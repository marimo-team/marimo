/* Copyright 2024 Marimo. All rights reserved. */

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
