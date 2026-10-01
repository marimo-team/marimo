/* Copyright 2026 Marimo. All rights reserved. */

export interface ResolvedExportLocale {
  tag: string;
  decimal_separator: string;
}

const FORBIDDEN_DECIMAL_SEPARATORS = new Set(["\r", "\n", "\0"]);

export function resolveExportLocale(locale: string): ResolvedExportLocale {
  if (locale === "") {
    throw new Error("Locale tag must be a non-empty string.");
  }

  const decimalSeparator = new Intl.NumberFormat(locale)
    .formatToParts(1.1)
    .find((part) => part.type === "decimal")?.value;

  if (
    decimalSeparator === undefined ||
    [...decimalSeparator].length !== 1 ||
    FORBIDDEN_DECIMAL_SEPARATORS.has(decimalSeparator)
  ) {
    throw new Error(
      `Locale "${locale}" did not resolve a valid decimal separator.`,
    );
  }

  return {
    tag: locale,
    decimal_separator: decimalSeparator,
  };
}
