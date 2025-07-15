/* Copyright 2024 Marimo. All rights reserved. */
import { startCase } from "lodash-es";
import { Logger } from "./Logger";

export const Strings = {
  /**
   * startCase that can handle non-letters
   */
  startCase: (str: string): string => {
    if (!str) {
      return "";
    }

    if (typeof str !== "string") {
      Logger.error(str);
      throw new TypeError(`Expected string, got ${typeof str}`);
    }

    // If has no letters, return the string
    if (!/[A-Za-z]/.test(str)) {
      return str;
    }

    return startCase(str);
  },

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
};

export const decodeUtf8 = (array: Uint8Array): string => {
  const str = new TextDecoder().decode(array);
  return str;
};
