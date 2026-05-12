/* Copyright 2026 Marimo. All rights reserved. */

import { AlertCircleIcon, KeyRoundIcon, Loader2Icon } from "lucide-react";
import React from "react";
import { Button } from "@/components/ui/button";
import {
  GauthParentBridgeError,
  startGoogleAuthFromParent,
} from "@/core/google-auth/parent-bridge";
import {
  type GauthErrorCode,
  type MarimoGauthResultMessage,
  PROTOCOL_VERSION,
} from "@/core/google-auth/types";
import { Logger } from "@/utils/Logger";

/**
 * Mimetype used on a stdin-channel message to request an OAuth-style auth
 * round-trip from the frontend. Owned by marimo (the channel) — the JSON
 * envelope shape inside `payload` is owned by external shim packages such
 * as `marimo-google-auth`. See plan.md §5 for the wire protocol.
 */
export const AUTH_REQUEST_MIMETYPE = "application/x-marimo-auth-request";

/**
 * Parsed kernel-side payload. Owned by the shim (`marimo-google-auth`);
 * we only consume the fields we need to drive the UI / bridge.
 */
interface AuthRequestPayload {
  request_id: string;
  provider: "google";
  scopes: string[];
  include_granted_scopes?: boolean;
  hosted_domain?: string | null;
}

interface ParseResult {
  payload: AuthRequestPayload | null;
  error: string | null;
}

function parsePayload(payload: string): ParseResult {
  let raw: unknown;
  try {
    raw = JSON.parse(payload);
  } catch (e) {
    return {
      payload: null,
      error: e instanceof Error ? e.message : String(e),
    };
  }
  if (typeof raw !== "object" || raw === null) {
    return { payload: null, error: "Payload is not a JSON object" };
  }
  // After `typeof === "object"` + the `in` operator, TS narrows
  // `raw` to include each property as `unknown` — no Record-cast
  // needed.
  const requestId =
    "request_id" in raw && typeof raw.request_id === "string"
      ? raw.request_id
      : null;
  const providerRaw =
    "provider" in raw && typeof raw.provider === "string" ? raw.provider : null;
  if (!requestId || !providerRaw) {
    return {
      payload: null,
      error: "Missing required field: request_id or provider",
    };
  }
  // Only "google" is supported; the bridge below is Google-specific.
  if (providerRaw !== "google") {
    return {
      payload: null,
      error: `Unsupported auth provider: ${providerRaw}`,
    };
  }
  const scopesRaw = "scopes" in raw ? raw.scopes : undefined;
  // `Array.isArray` widens to `any[]`; filter narrows each element.
  const scopes: string[] = Array.isArray(scopesRaw)
    ? scopesRaw.filter((s): s is string => typeof s === "string")
    : [];
  const includeGrantedScopes =
    "include_granted_scopes" in raw &&
    typeof raw.include_granted_scopes === "boolean"
      ? raw.include_granted_scopes
      : true;
  const hostedDomain =
    "hosted_domain" in raw && typeof raw.hosted_domain === "string"
      ? raw.hosted_domain
      : null;
  return {
    payload: {
      request_id: requestId,
      provider: "google",
      scopes,
      include_granted_scopes: includeGrantedScopes,
      hosted_domain: hostedDomain,
    },
    error: null,
  };
}

type BridgeState =
  | { phase: "probing" }
  // `needs_link` carries the user-click trigger that the iframe must
  // call synchronously inside `onClick`. We stash it on state so
  // the button's onClick stays a plain function (no async chain that
  // would break user-activation propagation).
  | {
      phase: "needs_link";
      missingScopes: string[];
      sendOpenLink: () => void;
    }
  | { phase: "linking" }
  | { phase: "error"; code: string; message: string };

/**
 * Inline cell-output card that drives a kernel-initiated Google OAuth
 * round-trip via the parent frame.
 *
 * State machine:
 *   probing → linking → (success) submit RESULT to kernel
 *   probing → needs_link → user click → linking → ...
 *   probing → error → user retries → probing
 */
export const AuthRequest: React.FC<{
  payload: string;
  onSubmit: (responseJson: string) => void;
}> = ({ payload, onSubmit }) => {
  const { payload: parsed, error: parseError } = React.useMemo(
    () => parsePayload(payload),
    [payload],
  );

  const [state, setState] = React.useState<BridgeState>({ phase: "probing" });
  // Bumped by Retry to re-run the effect; keeps the request_id stable
  // across retries (the parent is idempotent on request_id).
  const [retryNonce, setRetryNonce] = React.useState(0);

  const submittedRef = React.useRef(false);

  const submitResult = React.useCallback(
    (result: MarimoGauthResultMessage) => {
      if (submittedRef.current) {
        return;
      }
      submittedRef.current = true;
      const responseJson = JSON.stringify(result);
      Logger.log("[AuthRequest] submitting result to kernel", {
        requestId: result.request_id,
        status: result.status,
        bytes: responseJson.length,
      });
      onSubmit(responseJson);
    },
    [onSubmit],
  );

  const submitError = React.useCallback(
    (opts: { requestId: string; code: GauthErrorCode; message: string }) => {
      submitResult({
        type: "MARIMO_GAUTH_RESULT",
        protocol_version: PROTOCOL_VERSION,
        request_id: opts.requestId,
        status: "error",
        error_code: opts.code,
        error_message: opts.message,
      });
    },
    [submitResult],
  );

  React.useEffect(() => {
    if (!parsed) {
      return;
    }
    setState({ phase: "probing" });

    const handle = startGoogleAuthFromParent({
      requestId: parsed.request_id,
      scopes: parsed.scopes,
      includeGrantedScopes: parsed.include_granted_scopes,
      hostedDomain: parsed.hosted_domain ?? null,
      onNeedsLink: (msg, sendOpenLink) => {
        // Wrap `sendOpenLink` so the click handler can switch to
        // `linking` immediately for snappy feedback while we wait
        // for Clerk + Google.
        setState({
          phase: "needs_link",
          missingScopes: msg.missing_scopes,
          sendOpenLink: () => {
            sendOpenLink();
            setState({ phase: "linking" });
          },
        });
      },
    });

    handle.promise
      .then((result) => {
        submitResult(result);
      })
      .catch((err: unknown) => {
        if (err instanceof GauthParentBridgeError) {
          if (err.code === "parent_unavailable") {
            setState({
              phase: "error",
              code: err.code,
              message:
                "No parent frame available. Self-hosted browser sign-in is not enabled yet.",
            });
            submitError({
              requestId: parsed.request_id,
              code: "server_error",
              message:
                "Parent frame unavailable; self-hosted GIS fallback not implemented.",
            });
            return;
          }
          if (err.code === "user_cancelled") {
            // cancel() was called (e.g. on unmount). Don't surface.
            return;
          }
          setState({ phase: "error", code: err.code, message: err.message });
          submitError({
            requestId: parsed.request_id,
            code: err.code,
            message: err.message,
          });
          return;
        }
        const message = err instanceof Error ? err.message : String(err);
        setState({ phase: "error", code: "server_error", message });
        submitError({
          requestId: parsed.request_id,
          code: "server_error",
          message,
        });
      });

    return () => {
      handle.cancel();
    };
    // Re-run on retry — using the nonce as a dependency to trigger a
    // fresh effect without changing the request_id.
  }, [parsed, retryNonce, submitResult, submitError]);

  if (parseError != null || parsed == null) {
    return (
      <div className="flex flex-col gap-2 pt-2 rounded border border-(--red-6) bg-(--red-2) p-3 text-sm">
        <div className="flex items-center gap-2 font-medium text-(--red-11)">
          <AlertCircleIcon className="h-4 w-4" />
          Auth request payload invalid
        </div>
        <div className="text-xs text-(--red-11) font-mono">
          {parseError ?? "Missing fields"}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 pt-2 rounded border border-(--blue-6) bg-(--blue-2) p-3 text-sm">
      <div className="flex items-center gap-2 font-medium text-(--blue-11)">
        <KeyRoundIcon className="h-4 w-4" />
        Sign in to {prettyProvider(parsed.provider)}
        <span className="ml-auto font-mono text-xs text-(--slate-9)">
          req {parsed.request_id.slice(0, 8)}
        </span>
      </div>
      {parsed.scopes.length > 0 && <ScopeList scopes={parsed.scopes} />}
      {state.phase === "probing" && (
        <div className="flex items-center gap-2 text-xs text-(--slate-11)">
          <Loader2Icon className="h-3 w-3 animate-spin" />
          <span>Checking sign-in status…</span>
        </div>
      )}
      {state.phase === "needs_link" && (
        <div className="flex flex-col gap-2">
          <div className="text-xs text-(--slate-11)">
            You need to authorize {prettyProvider(parsed.provider)}{" "}
            {summarizeScopes(state.missingScopes)
              ? `for ${summarizeScopes(state.missingScopes)}`
              : ""}
            .
          </div>
          <div>
            <Button
              data-testid="auth-request-sign-in"
              size="sm"
              variant="default"
              // IMPORTANT: this onClick is intentionally synchronous.
              // `sendOpenLink` is a synchronous postMessage so the
              // browser propagates transient user activation across
              // the iframe/parent boundary and the parent's
              // `window.open()` is not popup-blocked.
              onClick={() => {
                state.sendOpenLink();
              }}
            >
              <GoogleGlyph className="mr-2 h-4 w-4" />
              Sign in with {prettyProvider(parsed.provider)}
            </Button>
          </div>
        </div>
      )}
      {state.phase === "linking" && (
        <div className="flex items-center gap-2 text-xs text-(--slate-11)">
          <Loader2Icon className="h-3 w-3 animate-spin" />
          <span>
            Waiting for {prettyProvider(parsed.provider)} sign-in to complete in
            the popup window…
          </span>
        </div>
      )}
      {state.phase === "error" && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-xs text-(--red-11)">
            <AlertCircleIcon className="h-3 w-3" />
            <span>
              {state.message}{" "}
              <span className="font-mono text-(--slate-9)">({state.code})</span>
            </span>
          </div>
          <div>
            <Button
              data-testid="auth-request-retry"
              size="sm"
              variant="outline"
              onClick={() => {
                submittedRef.current = false;
                setRetryNonce((n) => n + 1);
              }}
            >
              Retry
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

function prettyProvider(p: string): string {
  if (p === "google") {
    return "Google";
  }
  return p;
}

/**
 * Friendly-name a list of Google OAuth scopes for the inline copy.
 * Falls back to empty string when the bundle is too generic to
 * summarize — the surrounding sentence is written so an empty
 * summary still reads naturally.
 */
function summarizeScopes(scopes: string[]): string {
  const labels = new Set<string>();
  for (const s of scopes) {
    const meta = describeScope(s);
    if (meta) {
      labels.add(meta.shortLabel);
    }
  }
  if (labels.size === 0) {
    return "";
  }
  const arr = [...labels];
  if (arr.length === 1) {
    return arr[0] ?? "";
  }
  if (arr.length === 2) {
    return `${arr[0]} and ${arr[1]}`;
  }
  return `${arr.slice(0, -1).join(", ")}, and ${arr[arr.length - 1]}`;
}

interface ScopeMeta {
  /** Headline label used in the bulleted list and the short summary. */
  shortLabel: string;
  /** One-line plain-English description of what the scope grants. */
  description: string;
  /**
   * Sensitive scopes (per Google's verification taxonomy) deserve a
   * stronger visual treatment in the consent card. Currently used to
   * tag full Drive + GCS write scopes that grant broad data access.
   */
  sensitive: boolean;
}

/**
 * Map well-known Google OAuth scope URLs to a humane label.
 * Documenting these explicitly serves two purposes:
 *
 *   1. UX — users see "View and manage your Google Drive files",
 *      not `https://www.googleapis.com/auth/drive`.
 *   2. Security — a malicious
 *      notebook can request any scope it likes. The inline card is
 *      the only place a user sees what they're about to grant before
 *      clicking "Sign in". Surfacing the *meaning* of each scope, and
 *      flagging sensitive ones, lets a casual reader spot an
 *      out-of-place ask (e.g. a Drive notebook quietly requesting
 *      BigQuery write).
 *
 * Unknown scopes fall back to displaying the raw URL — visible by
 * design so the user can still inspect anything we haven't mapped.
 */
const SCOPE_META: Readonly<Record<string, ScopeMeta>> = {
  "https://www.googleapis.com/auth/userinfo.email": {
    shortLabel: "Email address",
    description: "See your primary Google account email address.",
    sensitive: false,
  },
  "https://www.googleapis.com/auth/userinfo.profile": {
    shortLabel: "Profile info",
    description: "See your name, profile picture, and locale.",
    sensitive: false,
  },
  "https://www.googleapis.com/auth/drive": {
    shortLabel: "Drive",
    description: "View, edit, create, and delete all your Google Drive files.",
    sensitive: true,
  },
  "https://www.googleapis.com/auth/drive.file": {
    shortLabel: "Drive (per-file)",
    description:
      "Create and edit only the Google Drive files this notebook opens.",
    sensitive: false,
  },
  "https://www.googleapis.com/auth/spreadsheets": {
    shortLabel: "Sheets",
    description: "Read and write your Google Sheets.",
    sensitive: false,
  },
  "https://www.googleapis.com/auth/bigquery": {
    shortLabel: "BigQuery",
    description: "Read and write data in your BigQuery datasets.",
    sensitive: false,
  },
  "https://www.googleapis.com/auth/devstorage.full_control": {
    shortLabel: "Cloud Storage",
    description: "Full read/write access to your Google Cloud Storage buckets.",
    sensitive: true,
  },
};

function describeScope(scope: string): ScopeMeta | null {
  return SCOPE_META[scope] ?? null;
}

const ScopeList: React.FC<{ scopes: string[] }> = ({ scopes }) => {
  return (
    <div className="flex flex-col gap-1 text-xs text-(--slate-11)">
      <div className="font-medium">This notebook is asking for:</div>
      <ul className="flex flex-col gap-1 pl-1">
        {scopes.map((scope) => {
          const meta = describeScope(scope);
          if (!meta) {
            // Unknown scope — show the raw URL so the user can still
            // inspect what's being asked for, plus a visual cue that
            // we don't have a friendly label for it.
            return (
              <li
                key={scope}
                className="flex items-start gap-1.5"
                data-testid="auth-request-scope-unknown"
              >
                <span aria-hidden="true">•</span>
                <span className="font-mono break-all">{scope}</span>
              </li>
            );
          }
          return (
            <li
              key={scope}
              className="flex items-start gap-1.5"
              data-testid={
                meta.sensitive
                  ? "auth-request-scope-sensitive"
                  : "auth-request-scope"
              }
            >
              <span aria-hidden="true">•</span>
              <span>
                <span
                  className={
                    meta.sensitive
                      ? "font-medium text-(--amber-11)"
                      : "font-medium"
                  }
                >
                  {meta.shortLabel}
                </span>
                {meta.sensitive && (
                  <span
                    className="ml-1 rounded px-1 text-[10px] uppercase tracking-wide bg-(--amber-3) text-(--amber-11)"
                    aria-label="Sensitive scope"
                  >
                    broad access
                  </span>
                )}
                <span className="ml-1">— {meta.description}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

function GoogleGlyph({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 48 48"
      aria-hidden="true"
      className={className}
    >
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.6-6 8-11.3 8a12 12 0 110-24c3 0 5.8 1.1 7.9 3l5.7-5.7A20 20 0 1024 44c11 0 20-9 20-20 0-1.3-.1-2.4-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7A20 20 0 006.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2c-2 1.3-4.4 2-7.2 2-5.3 0-9.7-3.4-11.3-8l-6.5 5C9.6 39.5 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4-4 5.4l6.2 5.2C40.6 35.6 44 30.3 44 24c0-1.3-.1-2.4-.4-3.5z"
      />
    </svg>
  );
}

/**
 * Read-only echo of a completed auth round-trip. Mirrors
 * `<StdInputWithResponse>` for the `text/plain` / `text/password` cases.
 */
export const AuthRequestWithResponse: React.FC<{
  payload: string;
  response?: string;
}> = ({ payload, response }) => {
  let requestId = "unknown";
  try {
    const parsed = JSON.parse(payload) as { request_id?: unknown };
    if (typeof parsed?.request_id === "string") {
      requestId = parsed.request_id;
    }
  } catch (e) {
    // Should never happen: payload was already parsed successfully when the
    // live prompt was rendered. Surface to the console for debuggability.
    Logger.warn("[AuthRequest] failed to parse historical payload", e);
  }
  let status = "submitted";
  if (response) {
    try {
      const parsed = JSON.parse(response) as { status?: unknown };
      if (typeof parsed?.status === "string") {
        status = parsed.status;
      }
    } catch (e) {
      // Response is JSON we ourselves stringified before sending to the
      // kernel; a parse failure here indicates a real regression.
      Logger.warn("[AuthRequest] failed to parse historical response", e);
    }
  }
  return (
    <div className="flex items-center gap-2 pt-2 text-xs text-(--slate-11)">
      <KeyRoundIcon className="h-3 w-3" />
      <span>Auth request</span>
      <span className="font-mono">req {requestId.slice(0, 8)}</span>
      <span className="ml-auto font-mono text-(--sky-11)">{status}</span>
    </div>
  );
};
