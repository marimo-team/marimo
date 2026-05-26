/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Wire protocol for the marimo google-auth bridge.
 *
 * This file **must stay in sync** with molab google auth types. We duplicate the
 * types (instead of publishing a shared package) so each side can be
 * iterated on independently; protocol bumps are coordinated via
 * `PROTOCOL_VERSION`.
 */

export const PROTOCOL_VERSION = 1;

export interface MarimoGauthRequestMessage {
  type: "MARIMO_GAUTH_REQUEST";
  protocol_version: number;
  request_id: string;
  provider: "google";
  scopes: string[];
  include_granted_scopes: boolean;
  hosted_domain: string | null;
}

/**
 * Parent → iframe. Non-terminal "we need a user click before we can
 * mint a token." See molab google auth types.
 */
export interface MarimoGauthNeedsLinkMessage {
  type: "MARIMO_GAUTH_NEEDS_LINK";
  protocol_version: number;
  request_id: string;
  missing_scopes: string[];
  additional_scopes: string[];
}

/**
 * Iframe → parent. MUST be sent synchronously inside the click
 * handler so transient user activation propagates across the
 * iframe/parent boundary and the parent's `window.open()` is not
 * popup-blocked.
 */
export interface MarimoGauthOpenLinkMessage {
  type: "MARIMO_GAUTH_OPEN_LINK";
  protocol_version: number;
  request_id: string;
  additional_scopes: string[];
}

export type MarimoGauthResultMessage =
  | MarimoGauthResultOkMessage
  | MarimoGauthResultErrorMessage;

export interface MarimoGauthResultOkMessage {
  type: "MARIMO_GAUTH_RESULT";
  protocol_version: number;
  request_id: string;
  status: "ok";
  access_token: string;
  expires_at: number;
  scope: string;
  token_type: "Bearer";
}

export interface MarimoGauthResultErrorMessage {
  type: "MARIMO_GAUTH_RESULT";
  protocol_version: number;
  request_id: string;
  status: "error";
  error_code: GauthErrorCode;
  error_message: string;
}

export type GauthErrorCode =
  | "unauthorized"
  | "user_cancelled"
  | "popup_blocked"
  | "scope_denied"
  | "link_required"
  | "parent_unavailable"
  | "rate_limited"
  | "server_error"
  | "timeout";

/**
 * Cast-free check that `value` is a string-only array. After
 * `Array.isArray` TypeScript widens to `any[]`, so we re-narrow each
 * element via `typeof` rather than asserting the array type.
 */
function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((s) => typeof s === "string");
}

const KNOWN_GAUTH_ERROR_CODES: readonly GauthErrorCode[] = [
  "unauthorized",
  "user_cancelled",
  "popup_blocked",
  "scope_denied",
  "link_required",
  "parent_unavailable",
  "rate_limited",
  "server_error",
  "timeout",
];

function isGauthErrorCode(value: unknown): value is GauthErrorCode {
  return (
    typeof value === "string" &&
    (KNOWN_GAUTH_ERROR_CODES as readonly string[]).includes(value)
  );
}

/**
 * Validates the envelope fields shared by every result variant
 * (`type` / `protocol_version` / `request_id`). The status-specific
 * payload check is layered on top by `isMarimoGauthResult` so each
 * variant only accepts its own required fields.
 */
function hasResultEnvelope(value: unknown): value is {
  type: "MARIMO_GAUTH_RESULT";
  protocol_version: number;
  request_id: string;
  status: unknown;
} {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return (
    "type" in value &&
    value.type === "MARIMO_GAUTH_RESULT" &&
    "protocol_version" in value &&
    typeof value.protocol_version === "number" &&
    "request_id" in value &&
    typeof value.request_id === "string" &&
    "status" in value
  );
}

function isMarimoGauthResultOk(
  value: unknown,
): value is MarimoGauthResultOkMessage {
  if (!hasResultEnvelope(value) || value.status !== "ok") {
    return false;
  }
  return (
    "access_token" in value &&
    typeof value.access_token === "string" &&
    "expires_at" in value &&
    typeof value.expires_at === "number" &&
    "scope" in value &&
    typeof value.scope === "string" &&
    "token_type" in value &&
    value.token_type === "Bearer"
  );
}

function isMarimoGauthResultError(
  value: unknown,
): value is MarimoGauthResultErrorMessage {
  if (!hasResultEnvelope(value) || value.status !== "error") {
    return false;
  }
  return (
    "error_code" in value &&
    isGauthErrorCode(value.error_code) &&
    "error_message" in value &&
    typeof value.error_message === "string"
  );
}

export function isMarimoGauthResult(
  value: unknown,
): value is MarimoGauthResultMessage {
  return isMarimoGauthResultOk(value) || isMarimoGauthResultError(value);
}

export function isMarimoGauthNeedsLink(
  value: unknown,
): value is MarimoGauthNeedsLinkMessage {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return (
    "type" in value &&
    value.type === "MARIMO_GAUTH_NEEDS_LINK" &&
    "protocol_version" in value &&
    typeof value.protocol_version === "number" &&
    "request_id" in value &&
    typeof value.request_id === "string" &&
    "missing_scopes" in value &&
    isStringArray(value.missing_scopes) &&
    "additional_scopes" in value &&
    isStringArray(value.additional_scopes)
  );
}

/**
 * The iframe never receives these messages — it only *sends* them.
 * These guards exist for symmetry with the molab bridge and
 * for cast-free assertions in tests.
 */
export function isMarimoGauthRequest(
  value: unknown,
): value is MarimoGauthRequestMessage {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return (
    "type" in value &&
    value.type === "MARIMO_GAUTH_REQUEST" &&
    "protocol_version" in value &&
    typeof value.protocol_version === "number" &&
    "request_id" in value &&
    typeof value.request_id === "string" &&
    "provider" in value &&
    value.provider === "google" &&
    "scopes" in value &&
    isStringArray(value.scopes)
  );
}

export function isMarimoGauthOpenLink(
  value: unknown,
): value is MarimoGauthOpenLinkMessage {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  return (
    "type" in value &&
    value.type === "MARIMO_GAUTH_OPEN_LINK" &&
    "protocol_version" in value &&
    typeof value.protocol_version === "number" &&
    "request_id" in value &&
    typeof value.request_id === "string" &&
    "additional_scopes" in value &&
    isStringArray(value.additional_scopes)
  );
}
