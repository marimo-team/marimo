/* Copyright 2024 Marimo. All rights reserved. */
import { KnownQueryParams } from "../constants";

export function createWsUrl(sessionId: string): string {
  const searchParams = new URLSearchParams(window.location.search);
  searchParams.set(KnownQueryParams.sessionId, sessionId);

  return `ws?${searchParams.toString()}`;
}
