/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { getBrowserLocale, isValidLocale } from "../browser-locale";

let mockNavigatorLanguage: string | undefined;

Object.defineProperty(window, "navigator", {
  value: {
    get language() {
      return mockNavigatorLanguage;
    },
  },
  writable: true,
});

describe("isValidLocale", () => {
  it("accepts standard BCP 47 tags", () => {
    expect(isValidLocale("en-US")).toBe(true);
    expect(isValidLocale("de-DE")).toBe(true);
  });

  it("rejects posix-style tags", () => {
    expect(isValidLocale("en-US@posix")).toBe(false);
  });
});

describe("getBrowserLocale", () => {
  beforeEach(() => {
    mockNavigatorLanguage = undefined;
  });

  afterEach(() => {
    mockNavigatorLanguage = undefined;
  });

  it("returns en-US when navigator.language is unset", () => {
    expect(getBrowserLocale()).toBe("en-US");
  });

  it("returns navigator.language when valid", () => {
    mockNavigatorLanguage = "de-DE";
    expect(getBrowserLocale()).toBe("de-DE");
  });

  it("falls back to en-US for invalid navigator.language", () => {
    mockNavigatorLanguage = "en-US@posix";
    expect(getBrowserLocale()).toBe("en-US");
  });
});
