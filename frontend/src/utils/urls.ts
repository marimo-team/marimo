/* Copyright 2024 Marimo. All rights reserved. */
import { generateSessionId } from "@/core/kernel/session";
import { asURL } from "./url";

export function updateQueryParams(updater: (params: URLSearchParams) => void) {
  const url = new URL(globalThis.location.href);
  updater(url.searchParams);
  globalThis.history.replaceState({}, "", url.toString());
}

export function hasQueryParam(key: string, value?: string): boolean {
  if (globalThis.window === undefined) {
    return false;
  }
  const urlParams = new URLSearchParams(globalThis.location.search);

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
