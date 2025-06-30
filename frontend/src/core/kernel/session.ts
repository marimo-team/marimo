/* Copyright 2024 Marimo. All rights reserved. */
import { init } from "@paralleldrive/cuid2";
import { Logger } from "@/utils/Logger";
import type { TypedString } from "@/utils/typed";
import { updateQueryParams } from "@/utils/urls";
import { KnownQueryParams } from "../constants";

export type SessionId = TypedString<"SessionId">;

const createId = init({ length: 6 });

export function generateSessionId(): SessionId {
  return `s_${createId()}` as SessionId;
}

export function isSessionId(value: string | null): value is SessionId {
  if (!value) {
    return false;
  }
  return /^s_[\da-z]{6}$/.test(value);
}

const sessionId = (() => {
  const url = new URL(globalThis.location.href);
  const id = url.searchParams.get(
    KnownQueryParams.sessionId,
  ) as SessionId | null;
  if (isSessionId(id)) {
    // Remove the session_id from the URL
    updateQueryParams((params) => {
      // Keep the session_id if we are in kiosk mode
      // this is so we can resume the same session if the user refreshes the page
      if (params.has(KnownQueryParams.kiosk)) {
        return;
      }
      params.delete(KnownQueryParams.sessionId);
    });
    Logger.debug("Connecting to existing session", { sessionId: id });
    return id;
  }
  Logger.debug("Starting a new session", { sessionId: id });
  return generateSessionId();
})();

/**
 * Resume an existing session or start a new one
 */
export function getSessionId(): SessionId {
  return sessionId;
}
