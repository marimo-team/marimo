/* Copyright 2023 Marimo. All rights reserved. */
import { store } from "@/core/state/jotai";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { useAtom } from "jotai";
import Cookies from "js-cookie";
import { atomWithStorage } from "jotai/utils";
import { SyncStorage } from "jotai/vanilla/utils/atomWithStorage";

export type Theme = "light" | "dark";

const createCookieStorage = <T>(): SyncStorage<T> => {
  const typed = Cookies.withConverter<T>({});
  return {
    getItem: (key: string, initialValue: T) => {
      return (typed.get(key) as T) ?? initialValue;
    },
    setItem: (key: string, value: T) => {
      typed.set(key, value);
    },
    removeItem: (key: string) => {
      typed.remove(key);
    },
  };
};

const themeAtom = atomWithStorage<Theme>(
  "marimo:theme",
  "light",
  // We use cookies instead of localStorage, so that the theme persists
  // between different ports on localhost.
  createCookieStorage<Theme>()
);

/**
 * React hook to manage the theme of the app.
 * This is stored in local storage, so it persists between page loads.
 */
export function useTheme() {
  const [theme, setTheme] = useAtom(themeAtom);

  if (getFeatureFlag("theming")) {
    return {
      theme,
      setTheme,
    };
  }

  // Dark theme is not ready so return light theme.
  return { theme: "light" as const, setTheme };
}

export function getTheme(): Theme {
  if (getFeatureFlag("theming")) {
    return store.get(themeAtom);
  }
  return "light";
}
