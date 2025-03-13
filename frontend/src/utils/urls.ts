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
