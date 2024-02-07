/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Resolve the path to a URL.
 *
 * If its a relative path, it will be resolved to the current origin.
 *
 * If document.baseURI is set, it will be used as the base URL.
 */
export function asURL(path: string): URL {
  if (path.startsWith("./")) {
    return new URL(path.slice(1), document.baseURI);
  }

  if (path.startsWith("/")) {
    return new URL(path, document.baseURI);
  }

  return new URL(path, document.baseURI);
}
