/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { resolvedMarimoConfigAtom } from "@/core/config/config";
import { isIslands } from "@/core/islands/utils";
import { store } from "@/core/state/jotai";

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
      document.body.dataset.mode === "dark" ||
      document.body.dataset.vscodeThemeKind === "vscode-dark" ||
      document.body.dataset.vscodeThemeKind === "vscode-high-contrast"
    ) {
      return "dark";
    }

    // Check the computed style for color-scheme
    const computedStyle = globalThis.getComputedStyle(document.body);
    const colorScheme = computedStyle.getPropertyValue("color-scheme").trim();
    if (colorScheme) {
      return colorScheme.includes("dark") ? "dark" : "light";
    }

    // Fallback: check for dark background color
    const bgColor = computedStyle.getPropertyValue("background-color");
    const rgb = bgColor.match(/\d+/g);
    if (rgb) {
      const [r, g, b] = rgb.map(Number);
      const brightness = (r * 299 + g * 587 + b * 114) / 1000;
      return brightness < 128 ? "dark" : "light";
    }

    // We don't want to infer from the system theme,
    // since the island consumer may not support dark mode.
    return "light";
  }

  return get(resolvedMarimoConfigAtom).display.theme;
});

const prefersDarkModeAtom = atom(false);

function setupThemeListener(): void {
  if (globalThis.window === undefined) {
    return;
  }
  if (!globalThis.matchMedia) {
    return;
  }

  const media = globalThis.matchMedia("(prefers-color-scheme: dark)");
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
