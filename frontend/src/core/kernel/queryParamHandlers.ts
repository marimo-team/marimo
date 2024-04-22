/* Copyright 2024 Marimo. All rights reserved. */
import { OperationMessageData } from "./handlers";

export const queryParamHandlers = {
  append: (data: OperationMessageData<"query-params-append">["data"]) => {
    const url = new URL(window.location.href);
    url.searchParams.append(data.key, data.value);
    window.history.pushState({}, "", `${url.pathname}${url.search}`);
    return;
  },
  set: (data: OperationMessageData<"query-params-set">["data"]) => {
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
  delete: (data: OperationMessageData<"query-params-delete">["data"]) => {
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
