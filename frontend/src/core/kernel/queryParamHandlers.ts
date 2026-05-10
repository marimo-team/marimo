/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessageData } from "./messages";

export const queryParamHandlers = {
  append: (data: NotificationMessageData<"query-params-append">) => {
    const url = new URL(window.location.href);
    url.searchParams.append(data.key, data.value);
    window.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  set: (data: NotificationMessageData<"query-params-set">) => {
    const url = new URL(window.location.href);
    if (Array.isArray(data.value)) {
      url.searchParams.delete(data.key);
      data.value.forEach((v) => url.searchParams.append(data.key, v));
    } else {
      url.searchParams.set(data.key, data.value);
    }
    window.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  delete: (data: NotificationMessageData<"query-params-delete">) => {
    const url = new URL(window.location.href);
    if (data.value == null) {
      url.searchParams.delete(data.key);
    } else {
      url.searchParams.delete(data.key, data.value);
    }
    window.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  clear: () => {
    const url = new URL(window.location.href);
    url.search = "";
    window.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
};

/**
 * Parse URL query parameters into the format expected by the kernel.
 */
export function parseQueryParams(): Record<string, string | string[]> {
  const url = new URL(window.location.href);
  const params: Record<string, string | string[]> = {};

  for (const [key, value] of url.searchParams.entries()) {
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
