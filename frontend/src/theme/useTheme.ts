/* Copyright 2023 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { userConfigAtom } from "@/core/config/config";

export type Theme = "light" | "dark";

/**
 * React hook to get the theme of the app.
 * This is stored in the user config.
 */
export function useTheme() {
  const userConfig = useAtomValue(userConfigAtom);
  return { theme: userConfig.display.theme };
}

export function getTheme(): Theme {
  return store.get(userConfigAtom).display.theme;
}

/**
 * Plugins are in a different react tree, so we cannot use useAtom as it looks
 * for an existing Provider in the react tree.
 * Instead we need to subscribe to the atom directly.
 */
export function useThemeForPlugin() {
  const [theme, setTheme] = useState(getTheme());
  useEffect(() => {
    return store.sub(userConfigAtom, () => {
      setTheme(getTheme());
    });
  }, []);

  return { theme };
}
