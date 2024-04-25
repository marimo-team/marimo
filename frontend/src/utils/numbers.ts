/* Copyright 2024 Marimo. All rights reserved. */
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
  // Only format if the value is not an integer
  if (value % 1 !== 0) {
    // Use mathjs for formatting with embedded numbers
    return format(value, { notation: "auto", precision: 4 });
  }

  return value.toString(); // Otherwise, return as is
}
