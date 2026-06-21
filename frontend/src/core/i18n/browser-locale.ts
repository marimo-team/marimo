/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Small duplicate of @react-aria/i18n getDefaultLocale logic for call sites
 * outside I18nProvider (e.g. settings UI). getDefaultLocale is not exported
 * from react-aria; LocaleProvider delegates to I18nProvider without a locale
 * prop for the browser-default case.
 */

export const DEFAULT_LOCALE = "en-US";

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
