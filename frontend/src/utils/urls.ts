/* Copyright 2024 Marimo. All rights reserved. */
import { generateSessionId } from "@/core/kernel/session";
import { asURL } from "./url";

export function updateQueryParams(updater: (params: URLSearchParams) => void) {
  const url = new URL(window.location.href);
  updater(url.searchParams);
  window.history.replaceState({}, "", url.toString());
}

export function hasQueryParam(key: string, value?: string): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const urlParams = new URLSearchParams(window.location.search);

  if (value === undefined) {
    return urlParams.has(key);
  }

  return urlParams.get(key) === value;
}

export function newNotebookURL() {
  const sessionId = generateSessionId();
  const initializationId = `__new__${sessionId}`;
  return asURL(`?file=${initializationId}`).toString();
}

const urlRegex = /^(https?:\/\/\S+)$/;
export function isUrl(value: unknown): boolean {
  return typeof value === "string" && urlRegex.test(value);
}

/**
 * Appends query parameters to an href, handling various edge cases.
 *
 * @param href - The href to append params to (e.g., "/path", "#/hash", "/path?existing=1", "/path#hash")
 * @param queryParams - URLSearchParams or query string to append
 * @param keys - Optional array of keys to filter which params to append
 * @returns The href with appended query parameters
 *
 * @example
 * appendQueryParams({ href: "/about", queryParams: new URLSearchParams("file=test.py") })
 * // Returns: "/about?file=test.py"
 *
 * @example
 * appendQueryParams({ href: "#/about", queryParams: "file=test.py&mode=edit", keys: ["file"] })
 * // Returns: "/?file=test.py#/about"
 *
 * @example
 * appendQueryParams({ href: "#/about?existing=1", queryParams: "file=test.py" })
 * // Returns: "#/about?existing=1&file=test.py"
 *
 * @example
 * appendQueryParams({ href: "/about?existing=1", queryParams: "file=test.py" })
 * // Returns: "/about?existing=1&file=test.py"
 *
 * @example
 * appendQueryParams({ href: "/about#section", queryParams: "file=test.py" })
 * // Returns: "/about?file=test.py#section"
 */
export function appendQueryParams({
  href,
  queryParams,
  keys,
}: {
  href: string;
  queryParams: URLSearchParams | string;
  keys?: string[];
}): string {
  // Convert queryParams to URLSearchParams if it's a string
  const params =
    typeof queryParams === "string"
      ? new URLSearchParams(queryParams)
      : queryParams;

  // If no params to append, return as is
  if (params.size === 0) {
    return href;
  }

  // Don't modify external links (full URLs)
  if (href.startsWith("http://") || href.startsWith("https://")) {
    return href;
  }

  // Special handling for hash-based routing
  const isHashBased = href.startsWith("#");
  const hasQueryInHash = isHashBased && href.includes("?");

  if (isHashBased && !hasQueryInHash) {
    // For hash-based hrefs without query params (e.g., #/about),
    // put query params on the main path before the hash: /?params#/route
    // This is common in SPAs where query params on the main URL need to be preserved
    const paramsToAdd = keys
      ? [...params.entries()].filter(([key]) => keys.includes(key))
      : [...params.entries()];

    const queryParams = new URLSearchParams();
    for (const [key, value] of paramsToAdd) {
      queryParams.set(key, value);
    }

    const queryString = queryParams.toString();
    if (!queryString) {
      return href;
    }

    return `/?${queryString}${href}`;
  }

  // Parse the href to extract parts for all other cases
  let basePath = href;
  let hash = "";
  let existingParams = new URLSearchParams();

  // For hash-based routing with query params, look for a second # to find actual hash fragment
  const hashSearchStart = isHashBased ? 1 : 0;
  const hashIndex = href.indexOf("#", hashSearchStart);

  if (hashIndex !== -1) {
    hash = href.slice(hashIndex);
    basePath = href.slice(0, hashIndex);
  }

  // Extract existing query params
  const queryIndex = basePath.indexOf("?");
  if (queryIndex !== -1) {
    existingParams = new URLSearchParams(basePath.slice(queryIndex + 1));
    basePath = basePath.slice(0, queryIndex);
  }

  // Merge params (new params overwrite existing ones with same key)
  const mergedParams = new URLSearchParams(existingParams);

  // Filter params by keys if provided
  const paramsToAdd = keys
    ? [...params.entries()].filter(([key]) => keys.includes(key))
    : [...params.entries()];

  for (const [key, value] of paramsToAdd) {
    mergedParams.set(key, value);
  }

  // Build the final URL
  const queryString = mergedParams.toString();
  if (!queryString) {
    return href;
  }

  return `${basePath}?${queryString}${hash}`;
}
