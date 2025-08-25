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
      getVsCodeTheme() === "dark"
    ) {
      return "dark";
    }

    // Check the computed style for color-scheme
    const computedStyle = window.getComputedStyle(document.body);
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

function getVsCodeTheme(): "light" | "dark" | undefined {
  const kind = document.body.dataset.vscodeThemeKind;
  if (kind === "vscode-dark") {
    return "dark";
  } else if (kind === "vscode-high-contrast") {
    return "dark";
  } else if (kind === "vscode-light") {
    return "light";
  }
  return undefined;
}

const codeThemeAtom = atom<"light" | "dark" | undefined>(getVsCodeTheme());

function setupVsCodeThemeListener() {
  const observer = new MutationObserver(() => {
    const theme = getVsCodeTheme();
    store.set(codeThemeAtom, theme);
  });
  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["data-vscode-theme-kind"],
  });
  return () => observer.disconnect();
}
setupVsCodeThemeListener();

export const resolvedThemeAtom = atom((get) => {
  const theme = get(themeAtom);
  const codeTheme = get(codeThemeAtom);
  if (codeTheme !== undefined) {
    return codeTheme;
  }
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
