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
