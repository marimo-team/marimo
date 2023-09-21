/* Copyright 2023 Marimo. All rights reserved. */
import { atom, useAtom } from "jotai";
import {
  AppConfig,
  UserConfig,
  parseAppConfig,
  parseUserConfig,
} from "../config/config";
import { store } from "./jotai";

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
