/* Copyright 2026 Marimo. All rights reserved. */
import { dequal } from "dequal";
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import { selectAtom } from "jotai/vanilla/utils";
import { cloneDeep, get, has, isPlainObject, mergeWith, set } from "lodash-es";
import { OverridingHotkeyProvider } from "../hotkeys/hotkeys";
import { type Platform, resolvePlatform } from "../hotkeys/shortcuts";
import { confirmedDocumentAtom } from "../session/active-notebook";
import { store } from "../state/jotai";
import {
  type AppConfig,
  defaultUserConfig,
  parseAppConfig,
  type UserConfig,
} from "./config-schema";

/**
 * Match Python configuration merging, including array and record replacement.
 */
export function mergeConfig<T extends object>(...sources: object[]): T {
  const result = {};
  for (const source of sources) {
    const replacements = [
      "keymap.overrides",
      "ai.custom_providers",
      "signing.trusted_signers",
    ]
      .filter((path) => has(source, path))
      .map((path) => {
        const previous = get(result, path);
        const incoming = get(source, path);
        const value =
          path !== "keymap.overrides" && isPlainObject(incoming)
            ? Object.fromEntries(
                Object.entries(incoming).map(([key, value]) => [
                  key,
                  isPlainObject(previous?.[key]) && isPlainObject(value)
                    ? { ...previous[key], ...(value as object) }
                    : value,
                ]),
              )
            : incoming;
        return { path, value };
      });
    mergeWith(result, source, (_obj: unknown, src: unknown) => {
      return Array.isArray(src) ? [...src] : undefined;
    });
    for (const { path, value } of replacements) {
      set(result, path, cloneDeep(value));
    }
  }
  return result as T;
}

/**
 * Atom for storing the user config.
 */
export const userConfigAtom = atom<UserConfig>(defaultUserConfig());

export const configOverridesAtom = atom<{}>({});

export const resolvedMarimoConfigAtom = atom<UserConfig>((get) => {
  const overrides = get(configOverridesAtom);
  const userConfig = get(userConfigAtom);
  return mergeConfig(userConfig, overrides);
});

export const autoInstantiateAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).runtime.auto_instantiate;
});

export const hotkeyOverridesAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).keymap.overrides ?? {};
});

export const platformAtom = atom<Platform>(resolvePlatform());

export const hotkeysAtom = atom((get) => {
  const overrides = get(hotkeyOverridesAtom);
  const platform = get(platformAtom);
  return new OverridingHotkeyProvider(overrides, { platform });
});

export const autoSaveConfigAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).save;
});

/**
 * The transport used to stream kernel messages from the server.
 * Experimental; configured via `server.transport`.
 */
export const connectionTransportTypeAtom = atom<"websocket" | "sse">((get) => {
  return get(resolvedMarimoConfigAtom).server.transport === "sse"
    ? "sse"
    : "websocket";
});

export const aiAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).ai;
});

export const completionAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).completion;
});

export const keymapPresetAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).keymap.preset;
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

export const aiModelConfiguredAtom = atom<boolean>((get) => {
  return isAiModelConfigured(get(resolvedMarimoConfigAtom));
});

export const aiFeaturesEnabledAtom = atom<boolean>((get) => {
  return isAiFeatureEnabled(get(resolvedMarimoConfigAtom));
});

export const editorFontSizeAtom = atom<number>((get) => {
  return get(resolvedMarimoConfigAtom).display.code_editor_font_size;
});

export const localeAtom = atom<string | null | undefined>((get) => {
  return get(resolvedMarimoConfigAtom).display.locale;
});

export function isAiEnabled(config: UserConfig) {
  return config.ai?.enabled !== false;
}

export function isAiModelConfigured(config: UserConfig) {
  return (
    Boolean(config.ai?.models?.chat_model) ||
    Boolean(config.ai?.models?.edit_model) ||
    Boolean(config.ai?.models?.autocomplete_model)
  );
}

export function isAiFeatureEnabled(config: UserConfig) {
  return isAiEnabled(config) && isAiModelConfigured(config);
}

/**
 * The app config the page was served with, as the server wrote it.
 *
 * The host document carries the current one; this holds its place until
 * that document arrives. It goes once every page carries its document.
 */
export const pageAppConfigAtom = atom<unknown>({});

/** The app config record in force, stable while its contents are. */
const appConfigRecordAtom = selectAtom(
  atom(
    (get) =>
      get(confirmedDocumentAtom)?.revision.app_config ?? get(pageAppConfigAtom),
  ),
  (record) => record,
  dequal,
);

/** The notebook's app config, as the host document carries it. */
export const appConfigAtom = atom((get) =>
  parseAppConfig(get(appConfigRecordAtom)),
);

export function useAppConfig(): AppConfig {
  return useAtomValue(appConfigAtom);
}

export function getAppConfig() {
  return store.get(appConfigAtom);
}

export const appWidthAtom = atom((get) => get(appConfigAtom).width);

/**
 * Snippets panel is available when user has custom paths or default snippets enabled.
 */
export const snippetsEnabledAtom = atom<boolean>((get) => {
  const config = get(resolvedMarimoConfigAtom);
  const customPaths = config.snippets?.custom_paths ?? [];
  const includeDefaultSnippets = config.snippets?.include_default_snippets;
  return customPaths.length > 0 || includeDefaultSnippets === true;
});

export const disableFileDownloadsAtom = atom<boolean>((get) => {
  return get(resolvedMarimoConfigAtom).server?.disable_file_downloads ?? false;
});
