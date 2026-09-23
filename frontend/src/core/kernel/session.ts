/* Copyright 2026 Marimo. All rights reserved. */
import { init } from "@paralleldrive/cuid2";
import { Logger } from "@/utils/Logger";
import type { TypedString } from "@/utils/typed";
import { updateQueryParams } from "@/utils/urls";
import { KnownQueryParams } from "../constants";
import { initialModeAtom } from "../mode";
import { store } from "../state/jotai";

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

let sessionId: SessionId | null = null;

function resolveSessionId(): SessionId {
  // Only the editor lets the URL steer the connection: kiosk mode and
  // external editors reattach to a running session through `session_id`.
  // An app served with `marimo run` never does. There, the session id is the
  // only thing that routes a browser to its kernel, so a link that picked it
  // would let the link's author attach to the reader's session afterwards,
  // and a stray `kiosk` flag would make the server refuse the connection.
  const urlMaySteerConnection = store.get(initialModeAtom) === "edit";

  const url = new URL(window.location.href);
  const id = url.searchParams.get(
    KnownQueryParams.sessionId,
  ) as SessionId | null;
  const urlSessionId = isSessionId(id) ? id : null;

  updateQueryParams((params) => {
    if (!urlMaySteerConnection) {
      params.delete(KnownQueryParams.sessionId);
      params.delete(KnownQueryParams.kiosk);
      return;
    }
    // Keep the session_id in kiosk mode so that a refresh resumes the same
    // session.
    if (params.has(KnownQueryParams.kiosk)) {
      return;
    }
    params.delete(KnownQueryParams.sessionId);
  });

  if (urlSessionId === null) {
    Logger.debug("Starting a new session", { sessionId: id });
    return generateSessionId();
  }
  if (!urlMaySteerConnection) {
    Logger.debug("Ignoring session_id from URL outside the editor", {
      sessionId: urlSessionId,
    });
    return generateSessionId();
  }
  Logger.debug("Connecting to existing session", { sessionId: urlSessionId });
  return urlSessionId;
}

/**
 * Resume an existing session or start a new one.
 *
 * Resolved on first use rather than at import time, because the URL is only
 * trusted once the app mode is known.
 */
export function getSessionId(): SessionId {
  if (sessionId === null) {
    sessionId = resolveSessionId();
  }
  return sessionId;
}
