/* Copyright 2024 Marimo. All rights reserved. */

export function prettyNumber(value: number | string): string {
  if (typeof value === "string") {
    return value;
  }

  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

export function prettyScientificNumber(value: number): string {
  // Handle special cases first
  if (value === 0) {
    return "0";
  } // Avoid displaying -0
  if (Number.isNaN(value)) {
    return "NaN";
  }
  if (!Number.isFinite(value)) {
    return value > 0 ? "Infinity" : "-Infinity";
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

  // Number has an integer part, format with 2 decimal places
  const formatter = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

  return formatter.format(value);
}
