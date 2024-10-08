/* Copyright 2024 Marimo. All rights reserved. */
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
