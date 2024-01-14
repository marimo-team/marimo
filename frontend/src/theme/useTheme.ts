/* Copyright 2023 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { atom, useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { userConfigAtom } from "@/core/config/config";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEMES: Theme[] = ["light", "dark", "system"];

const themeAtom = atom((get) => {
  return get(userConfigAtom).display.theme;
});

const prefersDarkModeAtom = atom(false);

function setupThemeListener(): void {
  if (typeof window === "undefined") {
    return;
  }

  const media = window.matchMedia("(prefers-color-scheme: dark)");
  store.set(prefersDarkModeAtom, media.matches);
  media.addEventListener("change", (e) => {
    store.set(prefersDarkModeAtom, e.matches);
  });
}
setupThemeListener();

const resolvedThemeAtom = atom((get) => {
  const theme = get(themeAtom);
  const prefersDarkMode = get(prefersDarkModeAtom);
  return theme === "system" ? (prefersDarkMode ? "dark" : "light") : theme;
});

/**
 * React hook to get the theme of the app.
 * This is stored in the user config.
 */
export function useTheme(): { theme: ResolvedTheme } {
  const theme = useAtomValue(resolvedThemeAtom);
  return { theme };
}

function getTheme(): ResolvedTheme {
  return store.get(resolvedThemeAtom);
}

/**
 * Plugins are in a different react tree, so we cannot use useAtom as it looks
 * for an existing Provider in the react tree.
 * Instead we need to subscribe to the atom directly.
 */
export function useThemeForPlugin(): { theme: ResolvedTheme } {
  const [theme, setTheme] = useState(getTheme());
  useEffect(() => {
    return store.sub(resolvedThemeAtom, () => {
      setTheme(getTheme());
    });
  }, []);

  return { theme };
}
