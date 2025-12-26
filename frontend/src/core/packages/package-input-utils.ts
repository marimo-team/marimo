/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Removes common package manager command prefixes from an input string.
 * This allows users to paste commands like "pip install httpx" and have
 * the "pip install" prefix automatically removed.
 *
 * @param input - The raw input string that may contain a package manager prefix
 * @returns The input with any recognized prefix removed and trimmed
 *
 * @example
 * stripPackageManagerPrefix("pip install httpx") // returns "httpx"
 * stripPackageManagerPrefix("uv add pandas numpy") // returns "pandas numpy"
 * stripPackageManagerPrefix("httpx") // returns "httpx"
 */
export function stripPackageManagerPrefix(input: string): string {
  const trimmedInput = input.trim();

  const prefixes = [
    "pip install",
    "pip3 install",
    "uv add",
    "uv pip install",
    "poetry add",
    "conda install",
    "pipenv install",
  ];

  for (const prefix of prefixes) {
    if (trimmedInput.toLowerCase().startsWith(prefix.toLowerCase())) {
      return trimmedInput.slice(prefix.length).trim();
    }
  }

  return trimmedInput;
}
