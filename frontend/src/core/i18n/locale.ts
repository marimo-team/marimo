/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Locale used when neither the configured locale nor the browser locale can be
 * resolved to a valid BCP 47 tag.
 */
export const FALLBACK_LOCALE = "en-US";

/**
 * Whether a tag is accepted by `Intl` (and therefore by react-aria's
 * `I18nProvider`, which constructs `Intl.Locale` internally).
 */
export function isValidLocale(locale: string): boolean {
  if (!locale) {
    return false;
  }
  try {
    new Intl.Locale(locale);
    return true;
  } catch {
    return false;
  }
}

/**
 * Coerce a browser or config locale tag into a valid
 * [BCP 47](https://www.rfc-editor.org/info/rfc5646) tag, or `null` if nothing
 * usable can be recovered.
 *
 * Some environments report POSIX-style tags that `Intl` rejects with
 * `RangeError: Incorrect locale information provided`, crashing anything that
 * constructs an `Intl.*` formatter (see issue #9938). Known offenders:
 * - POSIX modifiers, e.g. Chromium under Playwright reporting `en-US@posix`
 * - charset suffixes, e.g. `en_US.UTF-8`
 * - underscore separators, e.g. `en_US`
 */
export function normalizeLocale(tag: string | null | undefined): string | null {
  if (!tag) {
    return null;
  }

  const candidate = tag.split("@")[0].split(".")[0].trim().replaceAll("_", "-");

  if (isValidLocale(candidate)) {
    return candidate;
  }

  // Fall back to the language subtag alone (e.g. `en` from a mangled `en-XX`).
  const language = candidate.split("-")[0];
  if (isValidLocale(language)) {
    return language;
  }

  return null;
}

/** Resolve the browser's locale to a safe BCP 47 tag.
 * See https://github.com/marimo-team/marimo/issues/9938 */
export function browserLocale(): string {
  const language =
    typeof navigator === "undefined" ? undefined : navigator.language;
  return normalizeLocale(language) ?? FALLBACK_LOCALE;
}

/**
 * Resolve a configured locale to a safe BCP 47 tag, preferring the config and
 * falling back to the browser locale, then to {@link FALLBACK_LOCALE}.
 */
export function safeLocale(locale: string | null | undefined): string {
  return normalizeLocale(locale) ?? browserLocale();
}
