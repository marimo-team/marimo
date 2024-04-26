/* Copyright 2024 Marimo. All rights reserved. */

import { undefined } from "zod";
import { format } from "mathjs";

export function prettyNumber(value: number): string {
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
  const numberFormat = new Intl.NumberFormat("en-US", {
    notation: "scientific",
    maximumSignificantDigits: 2,
  });

  return Math.trunc(value) === 0
    ? // No integer part, use scientific notation
      format(value, { notation: "auto", precision: 2 })
    : // Number has an integer part, format with 2 decimal places
      value.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      });
}
