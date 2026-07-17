/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { configOverridesAtom, userConfigAtom } from "@/core/config/config";
import { defaultUserConfig } from "@/core/config/config-schema";
import { store } from "@/core/state/jotai";
import type { Theme } from "../useTheme";
import { resolvedThemeAtom, visibleForTesting } from "../useTheme";

const { themeFromQueryParam } = visibleForTesting;

function setQuery(search: string): void {
  window.history.replaceState({}, "", search === "" ? "/" : `/?${search}`);
}

function setConfigTheme(theme: Theme): void {
  const config = defaultUserConfig();
  store.set(userConfigAtom, {
    ...config,
    display: { ...config.display, theme },
  });
}

afterEach(() => {
  setQuery("");
  store.set(userConfigAtom, defaultUserConfig());
  store.set(configOverridesAtom, {});
});

describe("themeFromQueryParam", () => {
  it.each(["light", "dark", "system"] as const)(
    "returns the valid theme %s",
    (theme) => {
      setQuery(`theme=${theme}`);
      expect(themeFromQueryParam()).toBe(theme);
    },
  );

  it("returns undefined when the param is absent", () => {
    setQuery("");
    expect(themeFromQueryParam()).toBeUndefined();
  });

  it("returns undefined for an invalid value", () => {
    setQuery("theme=blue");
    expect(themeFromQueryParam()).toBeUndefined();
  });
});

describe("resolvedThemeAtom with a theme query param", () => {
  it("uses the saved config theme when no param is present", () => {
    setConfigTheme("dark");
    setQuery("");
    expect(store.get(resolvedThemeAtom)).toBe("dark");
  });

  it("lets the query param override the saved config theme", () => {
    setConfigTheme("light");
    setQuery("theme=dark");
    expect(store.get(resolvedThemeAtom)).toBe("dark");
  });

  it("falls back to the config theme for an invalid param value", () => {
    setConfigTheme("dark");
    setQuery("theme=blue");
    expect(store.get(resolvedThemeAtom)).toBe("dark");
  });
});
