/* Copyright 2023 Marimo. All rights reserved. */
export const Strings = {
  startCase: (str: string): string => {
    if (!str) {
      return "";
    }

    if (typeof str !== "string") {
      console.error(str);
      throw new TypeError(`Expected string, got ${typeof str}`);
    }

    return str
      .replaceAll("_", " ")
      .replaceAll(/([A-Z])/g, " $1")
      .replace(/^./, (str) => str.toUpperCase());
  },
};
