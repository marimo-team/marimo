/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtom } from "jotai";
import {
  AppConfig,
  UserConfig,
  parseAppConfig,
  parseUserConfig,
} from "./config-schema";
import { store } from "../state/jotai";

/**
 * Atom for storing the user config.
 */
export const userConfigAtom = atom<UserConfig>(parseUserConfig());

/**
 * Returns the user config.
 */
export function useUserConfig() {
  return useAtom(userConfigAtom);
}

export function getUserConfig() {
  return store.get(userConfigAtom);
}

export const aiEnabledAtom = atom<boolean>((get) => {
  return Boolean(get(userConfigAtom).ai.open_ai?.api_key);
});

/**
 * Atom for storing the app config.
 */
const appConfigAtom = atom<AppConfig>(parseAppConfig());

/**
 * Returns the app config.
 */
export function useAppConfig() {
  return useAtom(appConfigAtom);
}

export function getAppConfig() {
  return store.get(appConfigAtom);
}
