/* Copyright 2024 Marimo. All rights reserved. */

import type { OperationMessageData } from "./messages";

export const queryParamHandlers = {
  append: (data: OperationMessageData<"query-params-append">) => {
    const url = new URL(globalThis.location.href);
    url.searchParams.append(data.key, data.value);
    globalThis.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  set: (data: OperationMessageData<"query-params-set">) => {
    const url = new URL(globalThis.location.href);
    if (Array.isArray(data.value)) {
      url.searchParams.delete(data.key);
      data.value.forEach((v) => url.searchParams.append(data.key, v));
    } else {
      url.searchParams.set(data.key, data.value);
    }
    globalThis.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  delete: (data: OperationMessageData<"query-params-delete">) => {
    const url = new URL(globalThis.location.href);
    if (data.value == null) {
      url.searchParams.delete(data.key);
    } else {
      url.searchParams.delete(data.key, data.value);
    }
    globalThis.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  clear: () => {
    const url = new URL(globalThis.location.href);
    url.search = "";
    globalThis.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
};
