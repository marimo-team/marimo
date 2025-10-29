/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Escapes special characters in field names for Altair/Vega-Lite.
 * Matches the backend implementation in marimo/_data/charts.py
 *
 * Special characters that need escaping:
 * - . (dot)
 * - [ ] (brackets)
 * - : (colon)
 *
 * See: https://altair-viz.github.io/user_guide/troubleshooting.html#encodings-with-special-characters
 */
export function escapeFieldName(field: string | undefined): string | undefined {
  if (!field) {
    return field;
  }
  return field
    .replace(/\./g, "\\.")
    .replace(/\[/g, "\\[")
    .replace(/\]/g, "\\]")
    .replace(/:/g, "\\:");
}
