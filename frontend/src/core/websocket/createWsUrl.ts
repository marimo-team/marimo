/* Copyright 2024 Marimo. All rights reserved. */
import { Strings } from "@/utils/strings";
import { KnownQueryParams } from "../constants";

export function createWsUrl(sessionId: string): string {
  const searchParams = new URLSearchParams(window.location.search);
  searchParams.set(KnownQueryParams.sessionId, sessionId);

  return resolveToWsUrl(`ws?${searchParams.toString()}`);
}

export function resolveToWsUrl(
  relativeUrl: string,
): `ws://${string}` | `wss://${string}` {
  if (relativeUrl.startsWith("ws:") || relativeUrl.startsWith("wss:")) {
    return relativeUrl as `ws://${string}` | `wss://${string}`;
  }
  const baseUri = new URL(document.baseURI);
  const protocol = baseUri.protocol === "https:" ? "wss:" : "ws:";
  const host = baseUri.host;
  const pathname = baseUri.pathname;
  return `${protocol}//${host}${Strings.withoutTrailingSlash(pathname)}/${Strings.withoutLeadingSlash(relativeUrl)}`;
}
