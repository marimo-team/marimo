/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import {
  type AppConfig,
  type UserConfig,
  parseAppConfig,
  parseConfigOverrides,
  parseUserConfig,
} from "./config-schema";
import { store } from "../state/jotai";
import { OverridingHotkeyProvider } from "../hotkeys/hotkeys";
import { merge } from "lodash-es";

/**
 * Atom for storing the user config.
 */
export const userConfigAtom = atom<UserConfig>(parseUserConfig());

export const configOverridesAtom = atom<{}>(parseConfigOverrides());

export const resolvedMarimoConfigAtom = atom<UserConfig>((get) => {
  const overrides = get(configOverridesAtom);
  const userConfig = get(userConfigAtom);
  return merge({}, userConfig, overrides);
});

export const autoInstantiateAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).runtime.auto_instantiate;
});

export const hotkeyOverridesAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).keymap.overrides ?? {};
});

export const hotkeysAtom = atom((get) => {
  const overrides = get(hotkeyOverridesAtom);
  return new OverridingHotkeyProvider(overrides);
});

export const autoSaveConfigAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).save;
});

export const aiAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).ai;
});

/**
 * Returns the user config.
 */
export function useUserConfig() {
  return useAtom(userConfigAtom);
}

export function useResolvedMarimoConfig() {
  return [
    useAtomValue(resolvedMarimoConfigAtom),
    useSetAtom(userConfigAtom),
  ] as const;
}

export function getResolvedMarimoConfig() {
  return store.get(resolvedMarimoConfigAtom);
}

export const aiEnabledAtom = atom<boolean>((get) => {
  return isAiEnabled(get(resolvedMarimoConfigAtom));
});

export const editorFontSizeAtom = atom<number>((get) => {
  return get(resolvedMarimoConfigAtom).display.code_editor_font_size;
});

export function isAiEnabled(config: UserConfig) {
  return (
    Boolean(config.ai?.open_ai?.api_key) ||
    Boolean(config.ai?.anthropic?.api_key) ||
    Boolean(config.ai?.google?.api_key) ||
    Boolean(config.ai?.bedrock?.profile_name)
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
