/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type { ReactNode } from "react";
import { I18nProvider } from "react-aria-components";
import { localeAtom } from "@/core/config/config";

interface LocaleProviderProps {
  children: ReactNode;
}

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

  // language-only, e.g. `en` from `en-US@posix` after failures
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
    if (Intl.NumberFormat.supportedLocalesOf([normalized]).length === 0) {
      return false;
    }
    new Intl.Locale(normalized);
    return true;
  } catch {
    return false;
  }
}

export function safeLocale(locale: string | null | undefined): string {
  // Always return a BCP 47 tag. isValidLocale accepts underscore forms
  // (e.g. en_US) for validation only — I18nProvider/Intl need hyphens.
  if (locale && isValidLocale(locale)) {
    return normalizeBrowserLocale(locale);
  }
  return normalizeBrowserLocale(
    typeof navigator !== "undefined" ? navigator.language : undefined,
  );
}

export const LocaleProvider = ({ children }: LocaleProviderProps) => {
  const locale = useAtomValue(localeAtom);

  return <I18nProvider locale={safeLocale(locale)}>{children}</I18nProvider>;
};
