/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Resolve the path to a URL.
 *
 * If its a relative path, it will be resolved to the current origin.
 *
 * If document.baseURI is set, it will be used as the base URL.
 */
export function asURL(path: string): URL {
  return new URL(path, document.baseURI);
}
