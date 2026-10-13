/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import type { RunRequests, UpdateQueryParamsRequest } from "../network/types";

/**
 * Parse a URL search string into the shape the kernel's `mo.query_params()`
 * uses: a key that appears once maps to a string, a repeated key to a list.
 */
export function parseSearchParams(
  search: string,
): UpdateQueryParamsRequest["queryParams"] {
  const params: UpdateQueryParamsRequest["queryParams"] = {};
  for (const [key, value] of new URLSearchParams(search)) {
    const existing = params[key];
    if (existing === undefined) {
      params[key] = value;
    } else if (Array.isArray(existing)) {
      existing.push(value);
    } else {
      params[key] = [existing, value];
    }
  }
  return params;
}

/**
 * Keep the kernel's query params in sync with the browser's URL.
 *
 * When a cell sets `mo.query_params()`, the frontend pushes a history entry
 * (see `queryParamHandlers`). Going back or forward restores an earlier URL,
 * which only fires `popstate`; this listener reports the restored params to
 * the kernel so the cells that read them re-run.
 *
 * @returns a function that stops listening.
 */
export function syncQueryParamsOnNavigation(
  send: RunRequests["sendUpdateQueryParams"],
): () => void {
  const handlePopState = () => {
    send({ queryParams: parseSearchParams(window.location.search) }).catch(
      (error) => {
        Logger.warn("Failed to sync query params from the URL", error);
      },
    );
  };
  window.addEventListener("popstate", handlePopState);
  return () => {
    window.removeEventListener("popstate", handlePopState);
  };
}
