/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, describe, expect, it } from "vitest";
import { configOverridesAtom, userConfigAtom } from "@/core/config/config";
import { defaultUserConfig } from "@/core/config/config-schema";
import { store } from "@/core/state/jotai";
import type { Theme } from "../useTheme";
import { resolvedThemeAtom } from "../useTheme";

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

describe("resolvedThemeAtom", () => {
  it("uses the saved config theme", () => {
    setConfigTheme("dark");
    expect(store.get(resolvedThemeAtom)).toBe("dark");
    setConfigTheme("light");
    expect(store.get(resolvedThemeAtom)).toBe("light");
  });

  it.each(["light", "dark", "system", "blue"])(
    "ignores the theme query parameter %s",
    (theme) => {
      setQuery(`theme=${theme}`);
      setConfigTheme("dark");
      expect(store.get(resolvedThemeAtom)).toBe("dark");
      setConfigTheme("light");
      expect(store.get(resolvedThemeAtom)).toBe("light");
    },
  );

  it("uses resolved configuration overrides ahead of saved settings", () => {
    setConfigTheme("light");
    store.set(configOverridesAtom, { display: { theme: "dark" } });
    setQuery("theme=light");
    expect(store.get(resolvedThemeAtom)).toBe("dark");

    store.set(configOverridesAtom, {});
    expect(store.get(resolvedThemeAtom)).toBe("light");
  });
});
