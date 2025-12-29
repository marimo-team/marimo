/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Trims prefix and suffix from an AI completion response.
 * Handles the basic case where AI might include the original context in the response.
 */
export function trimAutocompleteResponse({
  response,
  prefix,
  suffix,
}: {
  response: string;
  prefix: string;
  suffix: string;
}): string {
  if (!response) {
    return response;
  }

  let trimmed = response;

  // Trim exact prefix match
  if (prefix && trimmed.startsWith(prefix)) {
    trimmed = trimmed.slice(prefix.length);
  }

  // Trim exact suffix match
  if (suffix && trimmed.endsWith(suffix)) {
    trimmed = trimmed.slice(0, -suffix.length);
  }

  return trimmed;
}
