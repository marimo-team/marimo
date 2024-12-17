/* Copyright 2024 Marimo. All rights reserved. */
import { assertExists } from "@/utils/assertExists";
import { invariant } from "@/utils/invariant";
import { isIslands } from "@/core/islands/utils";

interface MarimoSettings {
  getMarimoVersion: () => string;
  getMarimoServerToken: () => string;
  getMarimoAppConfig: () => unknown;
  getMarimoUserConfig: () => unknown;
  getMarimoConfigOverrides: () => unknown;
  getMarimoCode: () => string;
  getMarimoShowCode: () => boolean;
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
  getMarimoConfigOverrides: () => {
    try {
      return JSON.parse(getMarimoDOMValue("marimo-user-config", "overrides"));
    } catch {
      return {};
    }
  },
  getMarimoCode: () => {
    const tag = document.querySelector("marimo-code");
    invariant(tag, "internal-error: marimo-code not tag not found");
    const inner = tag.innerHTML;
    return decodeURIComponent(inner).trim();
  },
  getMarimoShowCode: () => {
    try {
      const tag = document.querySelector<HTMLElement>("marimo-code");
      invariant(tag, "internal-error: marimo-code not tag not found");
      const showCode = tag.dataset.showCode;
      if (showCode === "false") {
        return false;
      }
      return true;
    } catch {
      return true;
    }
  },
};

const islandsBasedMarimoSettings: MarimoSettings = {
  getMarimoVersion: () => {
    assertExists(import.meta.env.VITE_MARIMO_VERSION);
    return import.meta.env.VITE_MARIMO_VERSION;
  },
  getMarimoServerToken: () => {
    return "";
  },
  getMarimoConfigOverrides: () => {
    return {};
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
  getMarimoShowCode: () => {
    return true;
  },
};

export const {
  getMarimoVersion,
  getMarimoServerToken,
  getMarimoAppConfig,
  getMarimoUserConfig,
  getMarimoConfigOverrides,
  getMarimoCode,
  getMarimoShowCode,
} = isIslands() ? islandsBasedMarimoSettings : domBasedMarimoSettings;

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
