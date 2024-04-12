/* Copyright 2024 Marimo. All rights reserved. */
import { init } from "@paralleldrive/cuid2";
import { TypedString } from "@/utils/typed";
import { updateQueryParams } from "@/utils/urls";

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
  const url = new URL(window.location.href);
  const id = url.searchParams.get("session_id") as SessionId | null;
  if (isSessionId(id)) {
    // Remove the session_id from the URL
    updateQueryParams((params) => {
      params.delete("session_id");
    });
    return id;
  }
  return generateSessionId();
})();

/**
 * Resume an existing session or start a new one
 */
export function getSessionId(): SessionId {
  return sessionId;
}
