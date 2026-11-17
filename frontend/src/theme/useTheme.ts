/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { resolvedMarimoConfigAtom } from "@/core/config/config";
import { KnownQueryParams } from "@/core/constants";
import { isIslands } from "@/core/islands/utils";
import { store } from "@/core/state/jotai";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEMES: Theme[] = ["light", "dark", "system"];

function themeFromQueryParam(): Theme | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  const value = new URLSearchParams(window.location.search).get(
    KnownQueryParams.theme,
  );
  return THEMES.includes(value as Theme) ? (value as Theme) : undefined;
}

function getHostElements() {
  return [document.body, document.documentElement];
}

function getColorSchemeMedia() {
  return typeof window === "undefined"
    ? undefined
    : window.matchMedia?.("(prefers-color-scheme: dark)");
}

/** Body markers override HTML markers. CSS provides the fallback. */
function getHostTheme(
  prefersDark = getColorSchemeMedia()?.matches,
): ResolvedTheme {
  const elements = getHostElements();
  for (const element of elements) {
    for (const theme of ["dark", "light"] as const) {
      if (
        element.classList.contains(theme) ||
        element.classList.contains(`${theme}-mode`) ||
        element.classList.contains(`${theme}-theme`) ||
        element.dataset.theme === theme ||
        element.dataset.mode === theme
      ) {
        return theme;
      }
    }
  }

  const styles = elements.map((element) => window.getComputedStyle(element));
  const colorScheme = styles[0].colorScheme.split(/\s+/);
  if (colorScheme.includes("dark")) {
    return !colorScheme.includes("light") || prefersDark ? "dark" : "light";
  }
  if (colorScheme.includes("light")) {
    return "light";
  }

  // Transparent backgrounds do not indicate a dark host page.
  for (const style of styles) {
    const rgb = style.backgroundColor.match(/[\d.]+/g)?.map(Number);
    if (rgb && (rgb.length === 3 || rgb[3] > 0)) {
      const [r, g, b] = rgb;
      return (r * 299 + g * 587 + b * 114) / 1000 < 128 ? "dark" : "light";
    }
  }

  // A dark system preference does not imply a dark host.
  return "light";
}

const hostThemeAtom = atom<ResolvedTheme | undefined>(undefined);
hostThemeAtom.onMount = (setTheme) => {
  const media = getColorSchemeMedia();
  const updateTheme = () => setTheme(getHostTheme(media?.matches));
  const observer = new MutationObserver(updateTheme);
  for (const element of getHostElements()) {
    observer.observe(element, {
      attributes: true,
      attributeFilter: ["class", "data-theme", "data-mode", "style"],
    });
  }
  media?.addEventListener("change", updateTheme);
  updateTheme();
  return () => {
    observer.disconnect();
    media?.removeEventListener("change", updateTheme);
    // A later mount must read the current host theme.
    setTheme(undefined);
  };
};

const themeAtom = atom((get) => {
  if (isIslands()) {
    return get(hostThemeAtom) ?? getHostTheme();
  }
  return themeFromQueryParam() ?? get(resolvedMarimoConfigAtom).display.theme;
});

const prefersDarkModeAtom = atom(false);

function setupThemeListener(): void {
  const media = getColorSchemeMedia();
  if (!media) {
    return;
  }
  store.set(prefersDarkModeAtom, media.matches);
  media.addEventListener("change", (e) => {
    store.set(prefersDarkModeAtom, e.matches);
  });
}
setupThemeListener();

function getVsCodeTheme(): "light" | "dark" | undefined {
  const kind = document.body.dataset.vscodeThemeKind;
  switch (kind) {
    case "vscode-dark":
      return "dark";

    case "vscode-high-contrast":
      return "dark";

    case "vscode-light":
      return "light";

    // No default
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
 * Returns the resolved theme from VS Code, the Islands host, or notebook settings.
 */
export function useTheme(): { theme: ResolvedTheme } {
  const theme = useAtomValue(resolvedThemeAtom, { store });
  return { theme };
}

export const visibleForTesting = {
  themeFromQueryParam,
};
