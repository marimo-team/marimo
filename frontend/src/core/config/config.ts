/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtom, useSetAtom } from "jotai";
import {
  type AppConfig,
  type UserConfig,
  parseAppConfig,
  parseUserConfig,
} from "./config-schema";
import { store } from "../state/jotai";
import { OverridingHotkeyProvider } from "../hotkeys/hotkeys";

/**
 * Atom for storing the user config.
 */
export const userConfigAtom = atom<UserConfig>(parseUserConfig());

export const autoInstantiateAtom = atom((get) => {
  return get(userConfigAtom).runtime.auto_instantiate;
});

export const hotkeyOverridesAtom = atom((get) => {
  return get(userConfigAtom).keymap.overrides ?? {};
});

export const hotkeysAtom = atom((get) => {
  const overrides = get(hotkeyOverridesAtom);
  return new OverridingHotkeyProvider(overrides);
});

export const autoSaveConfigAtom = atom((get) => {
  return get(userConfigAtom).save;
});

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
  return isAiEnabled(get(userConfigAtom));
});

export function isAiEnabled(config: UserConfig) {
  return (
    Boolean(config.ai?.open_ai?.api_key) ||
    Boolean(config.ai?.anthropic?.api_key) ||
    Boolean(config.ai?.google?.api_key)
  );
}

/**
 * Atom for storing the app config.
 */
export const appConfigAtom = atom<AppConfig>(parseAppConfig());

/**
 * Returns the app config.
 */
export function useAppConfig() {
  return useAtom(appConfigAtom);
}

export function useSetAppConfig() {
  return useSetAtom(appConfigAtom);
}

export function getAppConfig() {
  return store.get(appConfigAtom);
}

export const appWidthAtom = atom((get) => get(appConfigAtom).width);
