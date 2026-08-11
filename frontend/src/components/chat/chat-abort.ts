/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessageChunk } from "ai";

/** Matches pydantic-ai / marimo AbortChunk.reason for user Stop. */
export const USER_CANCELLED_ABORT_REASON = "user_cancelled";

/**
 * Read an abort reason from a UI message stream chunk, if present.
 */
export function getAbortReasonFromChunk(
  chunk: UIMessageChunk,
): string | undefined {
  if (chunk.type !== "abort") {
    return undefined;
  }
  return chunk.reason;
}

/**
 * Resolve the abort reason for logging/UI. Client-side Stop often never
 * receives a server AbortChunk (the fetch is aborted first), so default to
 * user_cancelled when the turn ended as an abort.
 */
export function resolveChatAbortReason(opts: {
  isAbort: boolean;
  streamReason?: string | null;
}): string | null {
  if (!opts.isAbort) {
    return null;
  }
  return opts.streamReason || USER_CANCELLED_ABORT_REASON;
}

export function describeChatAbortReason(reason: string): string {
  switch (reason) {
    case USER_CANCELLED_ABORT_REASON:
      return "Generation stopped";
    case "timeout":
      return "Generation stopped: timed out";
    default:
      return `Generation stopped: ${reason}`;
  }
}
