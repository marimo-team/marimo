/* Copyright 2023 Marimo. All rights reserved. */
import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export type Theme = "light" | "dark";

const themeAtom = atomWithStorage<Theme>("marimo:theme", "light");

/**
 * React hook to manage the theme of the app.
 * This is stored in local storage, so it persists between page loads.
 */
export function useTheme() {
  const [theme, setTheme] = useAtom(themeAtom);

  if (process.env.NODE_ENV === "development") {
    return {
      theme,
      setTheme,
    };
  }

  // Dark theme is not ready so return light theme.
  return { theme: "light" as const, setTheme };
}
