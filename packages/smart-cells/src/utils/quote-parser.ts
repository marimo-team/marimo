/* Copyright 2024 Marimo. All rights reserved. */

import type { QuotePrefixKind, QuoteType } from "../types.js";
import { QUOTE_PREFIX_KINDS } from "../types.js";

/**
 * Split a quote string into its prefix (f/r/fr/rf) and the quote type.
 *
 * @param quote - The quote string (e.g., 'f"""', 'r"', '"""')
 * @returns A tuple of [prefix, quoteType]
 */
export function splitQuotePrefix(quote: string): [QuotePrefixKind, QuoteType] {
  // Start with the longest prefix to avoid partial matches
  const prefixKindsByLength = [...QUOTE_PREFIX_KINDS].sort(
    (a, b) => b.length - a.length,
  );

  for (const prefix of prefixKindsByLength) {
    if (quote.startsWith(prefix)) {
      return [prefix, quote.slice(prefix.length) as QuoteType];
    }
  }

  return ["", quote as QuoteType];
}

/**
 * Check if a quote type is a triple quote.
 */
export function isTripleQuote(quoteType: QuoteType): boolean {
  return quoteType === '"""' || quoteType === "'''";
}

/**
 * Get the matching closing quote for an opening quote.
 */
export function getClosingQuote(openingQuote: string): string {
  const [, quoteType] = splitQuotePrefix(openingQuote);
  return quoteType;
}
