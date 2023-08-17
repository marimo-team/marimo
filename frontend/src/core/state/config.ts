/* Copyright 2023 Marimo. All rights reserved. */
import { atom, useAtom } from "jotai";
import { AppConfig, UserConfig, getAppConfig, getUserConfig } from "../config";

/**
 * Atom for storing the user config.
 */
const userConfigAtom = atom<UserConfig>(getUserConfig());

/**
 * Returns the user config.
 */
export function useUserConfig() {
  return useAtom(userConfigAtom);
}

/**
 * Atom for storing the app config.
 */
const appConfigAtom = atom<AppConfig>(getAppConfig());

/**
 * Returns the app config.
 */
export function useAppConfig() {
  return useAtom(appConfigAtom);
}
