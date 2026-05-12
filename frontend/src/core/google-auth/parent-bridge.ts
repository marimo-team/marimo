/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Parent-frame bridge for the kernel's auth-request stdin channel.
 *
 * Round-trip lifecycle (deployer = marimo-cloud / molab):
 *   1. iframe (this module) → parent: `MARIMO_GAUTH_REQUEST`.
 *      Caller awaits the returned promise.
 *   2. parent → iframe: either
 *        - `MARIMO_GAUTH_RESULT` (terminal) — promise resolves, or
 *        - `MARIMO_GAUTH_NEEDS_LINK` (non-terminal) — caller's
 *          `onNeedsLink` callback fires with a `sendOpenLink`
 *          function bound to this request_id. `<AuthRequest>`
 *          renders the inline "Sign in" button.
 *   3. user clicks → `sendOpenLink` posts `MARIMO_GAUTH_OPEN_LINK`
 *      to the parent **synchronously inside the click handler** so
 *      transient user-activation propagates and the parent's
 *      `window.open()` is not popup-blocked.
 *   4. parent runs Clerk OAuth, polls /api/oauth/google/token,
 *      eventually sends `MARIMO_GAUTH_RESULT` — promise resolves.
 *
 * Self-hosted marimo (no parent frame): when `window.parent ===
 * window`, `start` rejects with `parent_unavailable`. The
 * AuthRequest UI surfaces a fallback message; a same-frame GIS
 * popup can be wired in there for deployers who want browser-only
 * sign-in.
 */

import { Deferred } from "@/utils/Deferred";
import { Logger } from "@/utils/Logger";
import {
  type GauthErrorCode,
  isMarimoGauthNeedsLink,
  isMarimoGauthResult,
  type MarimoGauthNeedsLinkMessage,
  type MarimoGauthRequestMessage,
  type MarimoGauthResultMessage,
  PROTOCOL_VERSION,
} from "./types";

export class GauthParentBridgeError extends Error {
  readonly code: GauthErrorCode | "parent_unavailable";
  constructor(code: GauthErrorCode | "parent_unavailable", message: string) {
    super(message);
    this.name = "GauthParentBridgeError";
    this.code = code;
  }
}

/**
 * Total time we allow a single auth round-trip to take from REQUEST
 * to terminal RESULT. Five minutes lines up with the parent-side
 * `POLL_TIMEOUT_MS` so both ends time out around the same time.
 */
const DEFAULT_TIMEOUT_MS = 5 * 60_000;

export interface StartGoogleAuthOptions {
  requestId: string;
  scopes: string[];
  includeGrantedScopes?: boolean;
  hostedDomain?: string | null;
  /**
   * Called when the parent reports that the user has not granted
   * one or more requested scopes. The callback receives the message
   * and a `sendOpenLink` function the UI **must** invoke
   * synchronously from the user's click handler — otherwise the
   * popup blocker will fire on the parent side.
   */
  onNeedsLink?: (
    msg: MarimoGauthNeedsLinkMessage,
    sendOpenLink: () => void,
  ) => void;
  /** Override default timeout. */
  timeoutMs?: number;
}

export interface StartGoogleAuthHandle {
  /** Resolves when the parent sends a terminal RESULT. */
  promise: Promise<MarimoGauthResultMessage>;
  /** Cancel the pending request and clean up the message listener. */
  cancel: () => void;
}

/**
 * Begin an auth round-trip with the parent frame.
 *
 * Returns a handle whose `promise` resolves with the terminal RESULT,
 * and a `cancel` function the caller can invoke on unmount. The
 * caller is responsible for invoking `sendOpenLink` synchronously
 * from a user click when `onNeedsLink` fires.
 */
export function startGoogleAuthFromParent(
  options: StartGoogleAuthOptions,
): StartGoogleAuthHandle {
  if (typeof window === "undefined" || window.parent === window) {
    return {
      promise: Promise.reject(
        new GauthParentBridgeError(
          "parent_unavailable",
          "No parent frame available (self-hosted or top-level page).",
        ),
      ),
      cancel: () => {
        // No-op: nothing to cancel when we never registered a listener.
      },
    };
  }

  const { requestId, scopes } = options;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  let settled = false;
  const deferred = new Deferred<MarimoGauthResultMessage>();

  const cleanup = () => {
    window.removeEventListener("message", onMessage);
    clearTimeout(timer);
  };

  function onMessage(event: MessageEvent) {
    if (settled) {
      return;
    }
    if (isMarimoGauthResult(event.data)) {
      const result = event.data;
      if (result.request_id !== requestId) {
        return;
      }
      if (result.protocol_version !== PROTOCOL_VERSION) {
        Logger.warn("[gauth] protocol version mismatch (RESULT)", {
          got: result.protocol_version,
          want: PROTOCOL_VERSION,
        });
      }
      settled = true;
      cleanup();
      deferred.resolve(result);
      return;
    }
    if (isMarimoGauthNeedsLink(event.data)) {
      const msg = event.data;
      if (msg.request_id !== requestId) {
        return;
      }
      if (msg.protocol_version !== PROTOCOL_VERSION) {
        Logger.warn("[gauth] protocol version mismatch (NEEDS_LINK)", {
          got: msg.protocol_version,
          want: PROTOCOL_VERSION,
        });
      }
      // Bind `sendOpenLink` to this request_id and additional scopes.
      // It MUST be invoked from a click handler synchronously.
      const sendOpenLink = () => {
        try {
          window.parent.postMessage(
            {
              type: "MARIMO_GAUTH_OPEN_LINK",
              protocol_version: PROTOCOL_VERSION,
              request_id: requestId,
              additional_scopes: msg.additional_scopes,
            },
            "*",
          );
        } catch (err) {
          Logger.error("[gauth] postMessage OPEN_LINK failed", { err });
        }
      };
      options.onNeedsLink?.(msg, sendOpenLink);
      return;
    }
  }

  const timer = setTimeout(() => {
    if (settled) {
      return;
    }
    settled = true;
    cleanup();
    deferred.reject(
      new GauthParentBridgeError(
        "timeout",
        `No response from parent frame within ${timeoutMs}ms`,
      ),
    );
  }, timeoutMs);

  window.addEventListener("message", onMessage);

  const request: MarimoGauthRequestMessage = {
    type: "MARIMO_GAUTH_REQUEST",
    protocol_version: PROTOCOL_VERSION,
    request_id: requestId,
    provider: "google",
    scopes,
    include_granted_scopes: options.includeGrantedScopes ?? true,
    hosted_domain: options.hostedDomain ?? null,
  };

  // targetOrigin is "*": the REQUEST carries no secrets, only the
  // scope list. The parent verifies the request shape and uses
  // `event.source`/`event.origin` to gate its reply.
  try {
    window.parent.postMessage(request, "*");
  } catch (err) {
    settled = true;
    cleanup();
    deferred.reject(
      new GauthParentBridgeError(
        "server_error",
        err instanceof Error ? err.message : String(err),
      ),
    );
  }

  return {
    promise: deferred.promise,
    cancel: () => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      deferred.reject(
        new GauthParentBridgeError(
          "user_cancelled",
          "Auth request cancelled by caller.",
        ),
      );
    },
  };
}
