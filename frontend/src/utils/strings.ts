/* Copyright 2026 Marimo. All rights reserved. */
import { Logger } from "./Logger";

/**
 * Capitalize the first character of a string.
 */
export function capitalize(str: string): string {
  if (!str) {
    return "";
  }
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Convert a string to start case (capitalize each word).
 * Handles camelCase, snake_case, kebab-case, and space-separated strings.
 * Returns the original string unchanged if it contains no letters.
 */
export function startCase(str: string): string {
  if (!str) {
    return "";
  }

  if (typeof str !== "string") {
    Logger.error(str);
    throw new TypeError(`Expected string, got ${typeof str}`);
  }

  // If has no letters, return the string as-is
  if (!/[A-Za-z]/.test(str)) {
    return str;
  }

  return str
    .replaceAll(/([\da-z])([A-Z])/g, "$1 $2") // camelCase → camel Case
    .replaceAll(/([A-Z]+)([A-Z][a-z])/g, "$1 $2") // ABCDef → ABC Def
    .replaceAll(/[\s_-]+/g, " ") // snake_case/kebab-case → spaces
    .trim()
    .split(" ")
    .map(capitalize)
    .join(" ");
}

export const Strings = {
  startCase,

  htmlEscape: (str: string | undefined): string | undefined => {
    if (!str) {
      return str;
    }
    return str
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;")
      .replaceAll("\n", " ");
  },

  withTrailingSlash(url: string): string {
    return url.endsWith("/") ? url : `${url}/`;
  },
  withoutTrailingSlash(url: string): string {
    return url.endsWith("/") ? url.slice(0, -1) : url;
  },
  withoutLeadingSlash(url: string): string {
    return url.startsWith("/") ? url.slice(1) : url;
  },
  asString: (value: unknown): string => {
    if (typeof value === "string") {
      return value;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  },
};

export const decodeUtf8 = (array: Uint8Array): string => {
  const str = new TextDecoder().decode(array);
  return str;
};
