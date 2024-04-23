/* Copyright 2024 Marimo. All rights reserved. */
import { assertExists } from "@/utils/assertExists";
import { invariant } from "@/utils/invariant";

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

// We don't control the DOM so we need to use a different method to get the values
const islandsBasedMarimoSettings: MarimoSettings = {
  getMarimoVersion: () => {
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

const {
  getMarimoVersion,
  getMarimoServerToken,
  getMarimoAppConfig,
  getMarimoUserConfig,
  getMarimoCode,
} = import.meta.env.VITE_MARIMO_ISLANDS
  ? islandsBasedMarimoSettings
  : domBasedMarimoSettings;

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
