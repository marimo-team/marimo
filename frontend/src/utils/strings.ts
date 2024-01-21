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
};
