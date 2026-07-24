/* Copyright 2026 Marimo. All rights reserved. */

/** Default when no configurable or browser locale is usable. */
export const FALLBACK_LOCALE = "en-US";

/**
 * Normalize browser / config locale tags for Intl and react-aria.
 *
 * Some Chromium/Playwright builds report tags like `en-US@posix` that throw
 * `RangeError: Incorrect locale information provided` when passed to Intl.
 */
export function normalizeBrowserLocale(tag: string | null | undefined): string {
  if (!tag) {
    return FALLBACK_LOCALE;
  }

  // Strip locale modifiers (`@posix`, `.UTF-8`) that are not BCP 47.
  let candidate = tag.split("@", 1)[0]?.trim() ?? "";
  const dotIdx = candidate.indexOf(".");
  if (dotIdx > 0) {
    candidate = candidate.slice(0, dotIdx);
  }
  // Underscores (some POSIX / Java locales) → BCP47 hyphens
  candidate = candidate.replaceAll("_", "-");

  if (candidate && isValidLocale(candidate)) {
    return candidate;
  }

  // language-only, e.g. `en` from a mangled tag after failures
  const language = candidate.split("-", 1)[0];
  if (language && isValidLocale(language)) {
    return language;
  }

  return FALLBACK_LOCALE;
}

export function isValidLocale(locale: string): boolean {
  try {
    // Reject modifiers that break Intl in some Chromium builds (`en-US@posix`).
    if (locale.includes("@") || locale.includes(".")) {
      return false;
    }
    const normalized = locale.replaceAll("_", "-");
    // supportedLocalesOf returns [] for unknown tags; more reliable than
    // NumberFormat which wrongly accepts many junk strings.
    if (
      typeof Intl === "undefined" ||
      typeof Intl.NumberFormat === "undefined" ||
      typeof Intl.NumberFormat.supportedLocalesOf !== "function"
    ) {
      // Extremely limited environments: accept BCP47-ish tags without Intl.
      return /^[A-Za-z]{2,3}(-[A-Za-z0-9]+)*$/.test(normalized);
    }
    if (Intl.NumberFormat.supportedLocalesOf([normalized]).length === 0) {
      return false;
    }
    // Intl.Locale is not available in every environment; do not treat that
    // as "invalid locale" (would force a global en-US fallback).
    if (typeof Intl.Locale === "function") {
      // Construct to reject structurally invalid tags supportedLocalesOf missed.
      new Intl.Locale(normalized);
    }
    return true;
  } catch {
    return false;
  }
}

export function safeLocale(locale: string | null | undefined): string {
  // Always return a BCP 47 tag. isValidLocale accepts underscore forms
  // (e.g. en_US) for validation only — I18nProvider/Intl need hyphens.
  //
  // Config values may also carry Chromium/POSIX modifiers (en-US@posix,
  // en_US.UTF-8). Prefer normalize-first so those recover the base tag
  // instead of being discarded as invalid and falling through to navigator.
  if (locale) {
    const fromConfig = normalizeBrowserLocale(locale);
    // If normalize recovered something other than pure fallback *or* the
    // input was already a usable locale that maps to FALLBACK_LOCALE (en-US),
    // use it. Only fall through to navigator when the config was empty/junk
    // and normalize had nothing to recover.
    if (fromConfig !== FALLBACK_LOCALE || isUsableLocaleInput(locale)) {
      return fromConfig;
    }
  }
  return normalizeBrowserLocale(
    typeof navigator !== "undefined" ? navigator.language : undefined,
  );
}

/** True when the raw input looks like it intentionally named a locale. */
function isUsableLocaleInput(locale: string): boolean {
  const stripped = locale.split("@", 1)[0]?.split(".", 1)[0]?.trim() ?? "";
  if (!stripped) {
    return false;
  }
  // After underscore→hyphen, does it validate?
  return isValidLocale(stripped.replaceAll("_", "-"));
}
