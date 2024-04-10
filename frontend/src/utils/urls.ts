/* Copyright 2024 Marimo. All rights reserved. */
export function updateQueryParams(updater: (params: URLSearchParams) => void) {
  const url = new URL(window.location.href);
  updater(url.searchParams);
  window.history.replaceState({}, "", url.toString());
}
