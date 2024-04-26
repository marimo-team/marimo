/* Copyright 2024 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { atom, useAtomValue } from "jotai";
import { userConfigAtom } from "@/core/config/config";
import { isIslands } from "@/core/islands/utils";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEMES: Theme[] = ["light", "dark", "system"];

const themeAtom = atom((get) => {
  // If it is islands, try a few ways to infer if it is dark mode.
  if (isIslands()) {
    // If it has a dark mode class on the body, use dark mode.
    if (
      document.body.classList.contains("dark-mode") ||
      document.body.classList.contains("dark")
    ) {
      return "dark";
    }
    // If it has data-theme=dark or data-mode=dark on the body, use dark mode.
    if (
      document.body.dataset.theme === "dark" ||
      document.body.dataset.mode === "dark"
    ) {
      return "dark";
    }
    // We don't want to infer from the system theme,
    // since the island consumer may not support dark mode.
    return "light";
  }

  return get(userConfigAtom).display.theme;
});

const prefersDarkModeAtom = atom(false);

function setupThemeListener(): void {
  if (typeof window === "undefined") {
    return;
  }
  if (!window.matchMedia) {
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
  const theme = useAtomValue(resolvedThemeAtom, { store });
  return { theme };
}
