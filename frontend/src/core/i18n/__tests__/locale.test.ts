/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it, vi } from "vitest";
import {
  browserLocale,
  FALLBACK_LOCALE,
  isValidLocale,
  normalizeLocale,
  safeLocale,
} from "../locale";

describe("isValidLocale", () => {
  it("accepts valid BCP 47 tags", () => {
    expect(isValidLocale("en-US")).toBe(true);
    expect(isValidLocale("de-DE")).toBe(true);
    expect(isValidLocale("en")).toBe(true);
  });

  it("rejects empty and modifier-tainted tags", () => {
    expect(isValidLocale("")).toBe(false);
    expect(isValidLocale("en-US@posix")).toBe(false);
    expect(isValidLocale("en_US.UTF-8")).toBe(false);
  });
});

describe("normalizeLocale", () => {
  it("keeps valid tags unchanged, including script + region", () => {
    expect(normalizeLocale("de-DE")).toBe("de-DE");
    expect(normalizeLocale("zh-Hant-TW")).toBe("zh-Hant-TW");
  });

  it("strips POSIX @modifiers (issue #9938)", () => {
    expect(normalizeLocale("en-US@posix")).toBe("en-US");
    expect(normalizeLocale("de-DE@euro")).toBe("de-DE");
    // ICU-style unicode extension keywords are also dropped.
    expect(normalizeLocale("de@collation=phonebook")).toBe("de");
  });

  it("strips charset suffixes and maps underscores", () => {
    expect(normalizeLocale("en_US.UTF-8")).toBe("en-US");
    expect(normalizeLocale("en_US")).toBe("en-US");
  });

  it("falls back to the language subtag when the full tag is invalid", () => {
    // `-toolongsubtag` / `-oed` are structurally invalid, so `Intl.Locale`
    // rejects the whole tag but accepts the leading `en`.
    expect(normalizeLocale("en-toolongsubtag")).toBe("en");
    expect(normalizeLocale("en-GB-oed")).toBe("en");
  });

  it("returns null for empty or unrecoverable tags", () => {
    expect(normalizeLocale(null)).toBeNull();
    expect(normalizeLocale(undefined)).toBeNull();
    expect(normalizeLocale("")).toBeNull();
    expect(normalizeLocale("@@@")).toBeNull();
    // POSIX `C` locale: single-letter tag is not a valid language subtag.
    expect(normalizeLocale("C")).toBeNull();
  });
});

describe("browserLocale", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("normalizes navigator.language", () => {
    vi.stubGlobal("navigator", { language: "en-US@posix" });
    expect(browserLocale()).toBe("en-US");
  });

  it("falls back when navigator.language is unusable", () => {
    vi.stubGlobal("navigator", { language: "@@@" });
    expect(browserLocale()).toBe(FALLBACK_LOCALE);
  });

  it("falls back when navigator is unavailable", () => {
    vi.stubGlobal("navigator", undefined);
    expect(browserLocale()).toBe(FALLBACK_LOCALE);
  });
});

describe("safeLocale", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("prefers a valid configured locale", () => {
    vi.stubGlobal("navigator", { language: "de-DE" });
    expect(safeLocale("fr-FR")).toBe("fr-FR");
  });

  it("normalizes configured locales before use", () => {
    vi.stubGlobal("navigator", { language: "de-DE" });
    expect(safeLocale("en_US")).toBe("en-US");
    expect(safeLocale("en-US@posix")).toBe("en-US");
  });

  it("falls back to the browser locale when config is unusable", () => {
    vi.stubGlobal("navigator", { language: "de-DE" });
    expect(safeLocale(null)).toBe("de-DE");
    expect(safeLocale("@@@")).toBe("de-DE");
  });

  it("normalizes the browser locale on the fallback path", () => {
    vi.stubGlobal("navigator", { language: "en-US@posix" });
    expect(safeLocale(null)).toBe("en-US");
  });

  it("falls back to FALLBACK_LOCALE when nothing is usable", () => {
    vi.stubGlobal("navigator", { language: "@@@" });
    expect(safeLocale(null)).toBe(FALLBACK_LOCALE);
  });
});
