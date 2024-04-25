/* Copyright 2024 Marimo. All rights reserved. */
import { assertExists } from "@/utils/assertExists";
import { invariant } from "@/utils/invariant";
import { isIslands } from "@/core/islands/utils";

interface MarimoSettings {
  getMarimoVersion: () => string;
  getMarimoServerToken: () => string;
  getMarimoAppConfig: () => unknown;
  getMarimoUserConfig: () => unknown;
  getMarimoCode: () => string;
}

const domBasedMarimoSettings: MarimoSettings = {
  getMarimoVersion: () => {
    return getMarimoDOMValue("marimo-version", "version");
  },
  getMarimoServerToken: () => {
    return getMarimoDOMValue("marimo-server-token", "token");
  },
  getMarimoAppConfig: () => {
    return JSON.parse(getMarimoDOMValue("marimo-app-config", "config"));
  },
  getMarimoUserConfig: () => {
    return JSON.parse(getMarimoDOMValue("marimo-user-config", "config"));
  },
  getMarimoCode: () => {
    const tag = document.querySelector("marimo-code");
    invariant(tag, "internal-error: marimo-code not tag not found");
    const inner = tag.innerHTML;
    return decodeURIComponent(inner).trim();
  },
};

// We have limited access to the DOM, so defaults are provided.
const islandsBasedMarimoSettings: MarimoSettings = {
  getMarimoVersion: () => {
    if (import.meta.env.VITE_MARIMO_VERSION === undefined) {
      // Version set by export, but can be overridden by ENV.
      return getMarimoDOMValue("marimo-version", "version");
    }
    assertExists(import.meta.env.VITE_MARIMO_VERSION);
    return import.meta.env.VITE_MARIMO_VERSION;
  },
  getMarimoServerToken: () => {
    return "";
  },
  getMarimoAppConfig: () => {
    return {};
  },
  getMarimoUserConfig: () => {
    return {};
  },
  getMarimoCode: () => {
    return "";
  },
};

function getMarimoSettingLookup<T extends keyof MarimoSettings>(
  settingName: T,
): () => ReturnType<MarimoSettings[T]> {
  return () => {
    // DOM isn't accessible at time of lookup, so defer to callback
    const result = isIslands()
      ? islandsBasedMarimoSettings[settingName]()
      : domBasedMarimoSettings[settingName]();
    return result as ReturnType<MarimoSettings[T]>;
  };
}

const MarimoSettingsWrapper: MarimoSettings = {
  getMarimoVersion: getMarimoSettingLookup("getMarimoVersion"),
  getMarimoServerToken: getMarimoSettingLookup("getMarimoServerToken"),
  getMarimoAppConfig: getMarimoSettingLookup("getMarimoAppConfig"),
  getMarimoUserConfig: getMarimoSettingLookup("getMarimoUserConfig"),
  getMarimoCode: getMarimoSettingLookup("getMarimoCode"),
};

const {
  getMarimoVersion,
  getMarimoServerToken,
  getMarimoAppConfig,
  getMarimoUserConfig,
  getMarimoCode,
} = MarimoSettingsWrapper;

export {
  getMarimoVersion,
  getMarimoServerToken,
  getMarimoAppConfig,
  getMarimoUserConfig,
  getMarimoCode,
};

function getMarimoDOMValue(tagName: string, key: string) {
  const tag = document.querySelector(tagName);
  invariant(
    tag !== null && tag instanceof HTMLElement,
    `internal-error: ${tagName} tag not found`,
  );

  const value = tag.dataset[key];
  invariant(
    value !== undefined,
    `internal-error: ${tagName} tag does not have ${key}`,
  );

  return value;
}
