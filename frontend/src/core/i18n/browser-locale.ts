/* Copyright 2026 Marimo. All rights reserved. */

const DEFAULT_LOCALE = "en-US";

/** Matches @react-aria/i18n getDefaultLocale validation. */
export function isValidLocale(locale: string): boolean {
  try {
    Intl.DateTimeFormat.supportedLocalesOf([locale]);
    return true;
  } catch {
    return false;
  }
}

/** Matches @react-aria/i18n getDefaultLocale browser fallback. */
export function getBrowserLocale(): string {
  const language =
    typeof navigator !== "undefined" &&
    (navigator.language ||
      (navigator as Navigator & { userLanguage?: string }).userLanguage);

  if (!language) {
    return DEFAULT_LOCALE;
  }

  if (isValidLocale(language)) {
    return language;
  }

  return DEFAULT_LOCALE;
}
