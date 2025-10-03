/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "./Logger";
import { memoizeLastValue } from "./once";

/**
 * Browsers have a limit on the maximum number of fractional digits they can display.
 * This function finds the maximum number of fractional digits that can be displayed for a given locale.
 */
export const maxFractionalDigits = memoizeLastValue((locale: string) => {
  const options = [100, 20, 2, 0];
  for (const option of options) {
    try {
      new Intl.NumberFormat(locale, {
        minimumFractionDigits: 0,
        maximumFractionDigits: option,
      }).format(1);
      return option;
    } catch (e) {
      Logger.error(e);
    }
  }
  return 0;
});

export function prettyNumber(value: unknown, locale: string): string {
  if (value === undefined || value === null) {
    return "";
  }

  if (Array.isArray(value)) {
    return String(value);
  }

  if (typeof value === "string") {
    return value;
  }

  if (typeof value === "boolean") {
    return String(value);
  }

  if (typeof value === "number" || typeof value === "bigint") {
    return value.toLocaleString(locale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    });
  }

  return String(value);
}

function scientificSpecialCase(value: number): string | null {
  if (value === 0) {
    return "0";
  } // Avoid displaying -0
  if (Number.isNaN(value)) {
    return "NaN";
  }
  if (!Number.isFinite(value)) {
    return value > 0 ? "Infinity" : "-Infinity";
  }

  // No special case
  return null;
}

export function prettyScientificNumber(
  value: number,
  opts: {
    shouldRound?: boolean; // Default to false
    locale: string;
  },
): string {
  // Handle special cases first
  const specialCase = scientificSpecialCase(value);
  if (specialCase !== null) {
    return specialCase;
  }

  // Determine if the number should be in scientific notation
  const absValue = Math.abs(value);
  if (absValue < 1e-2 || absValue >= 1e6) {
    return new Intl.NumberFormat(opts.locale, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
      notation: "scientific",
    })
      .format(value)
      .toLowerCase();
  }

  const { shouldRound, locale } = opts;

  if (shouldRound) {
    // Number has an integer part, format with 2 decimal places
    return new Intl.NumberFormat(locale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(value);
  }

  // Don't round
  return value.toLocaleString(locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: maxFractionalDigits(locale),
  });
}

const prefixes = {
  "24": "Y",
  "21": "Z",
  "18": "E",
  "15": "P",
  "12": "T",
  "9": "G",
  "6": "M",
  "3": "k",
  "0": "",
  "-3": "m",
  "-6": "µ",
  "-9": "n",
  "-12": "p",
  "-15": "f",
  "-18": "a",
  "-21": "z",
  "-24": "y",
};

export function prettyEngineeringNumber(value: number, locale: string): string {
  // Handle special cases first
  const specialCase = scientificSpecialCase(value);
  if (specialCase !== null) {
    return specialCase;
  }

  const [mant, exp] = new Intl.NumberFormat(locale, {
    notation: "engineering",
    maximumSignificantDigits: 3,
  })
    .format(value)
    .split("E");

  if (exp in prefixes) {
    return mant + prefixes[exp as keyof typeof prefixes];
  }

  return `${mant}E${exp}`;
}
