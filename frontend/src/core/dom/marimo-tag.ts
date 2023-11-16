/* Copyright 2023 Marimo. All rights reserved. */

import { invariant } from "@/utils/invariant";

export function getMarimoVersion(): string {
  return getMarimoDOMValue("marimo-version", "version");
}

export function getMarimoServerToken(): string {
  return getMarimoDOMValue("marimo-server-token", "config");
}

export function getRawMarimoAppConfig(): string {
  return getMarimoDOMValue("marimo-app-config", "config");
}

export function getRawMarimoUserConfig(): string {
  return getMarimoDOMValue("marimo-user-config", "config");
}

function getMarimoDOMValue(tagName: string, key: string) {
  const tag = document.querySelector(tagName);
  invariant(
    tag !== null && tag instanceof HTMLElement,
    `internal-error: ${tagName} tag not found`
  );

  const value = tag.dataset[key];
  invariant(
    value !== undefined,
    `internal-error: ${tagName} tag does not have ${key}`
  );

  return value;
}
