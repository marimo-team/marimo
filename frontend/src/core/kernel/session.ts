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
  const url = new URL(window.location.href);
  const id = url.searchParams.get(
    KnownQueryParams.sessionId,
  ) as SessionId | null;
  if (!isSessionId(id)) {
    Logger.debug("Starting a new session", { sessionId: id });
    return generateSessionId();
  }

  // Only the editor lets the URL choose the session id (kiosk mode and
  // external editors reattach to a running session that way). An app served
  // with `marimo run` never does: the session id is the only thing that
  // routes a browser to its kernel, so a link that picked the id would let
  // the author of that link attach to the reader's session afterwards.
  const urlMayPickSession = store.get(initialModeAtom) === "edit";

  updateQueryParams((params) => {
    // Keep the session_id in kiosk mode so that a refresh resumes the same
    // session.
    if (urlMayPickSession && params.has(KnownQueryParams.kiosk)) {
      return;
    }
    params.delete(KnownQueryParams.sessionId);
  });

  if (!urlMayPickSession) {
    Logger.debug("Ignoring session_id from URL outside the editor", {
      sessionId: id,
    });
    return generateSessionId();
  }

  Logger.debug("Connecting to existing session", { sessionId: id });
  return id;
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
