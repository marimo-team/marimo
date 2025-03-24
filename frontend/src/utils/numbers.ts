/* Copyright 2024 Marimo. All rights reserved. */

export function prettyNumber(
  value: number | string | undefined | null | boolean | unknown[],
): string {
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

  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
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
    // Default to false
    shouldRound?: boolean;
  } = {},
): string {
  // Handle special cases first
  const specialCase = scientificSpecialCase(value);
  if (specialCase !== null) {
    return specialCase;
  }

  // Determine if the number should be in scientific notation
  const absValue = Math.abs(value);
  if (absValue < 1e-2 || absValue >= 1e6) {
    return new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
      notation: "scientific",
    })
      .format(value)
      .toLowerCase();
  }

  const { shouldRound } = opts;

  if (shouldRound) {
    // Number has an integer part, format with 2 decimal places
    return new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(value);
  }

  // Don't round
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 100,
  }).format(value);
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

export function prettyEngineeringNumber(value: number): string {
  // Handle special cases first
  const specialCase = scientificSpecialCase(value);
  if (specialCase !== null) {
    return specialCase;
  }

  const [mant, exp] = new Intl.NumberFormat("en-us", {
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
