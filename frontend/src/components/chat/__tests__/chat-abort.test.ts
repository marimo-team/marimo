/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessageChunk } from "ai";
import { describe, expect, it } from "vitest";
import {
  describeChatAbortReason,
  getAbortReasonFromChunk,
  resolveChatAbortReason,
  USER_CANCELLED_ABORT_REASON,
} from "../chat-abort";

describe("chat-abort", () => {
  it("reads reason from abort chunks", () => {
    const chunk: UIMessageChunk = {
      type: "abort",
      reason: USER_CANCELLED_ABORT_REASON,
    };
    expect(getAbortReasonFromChunk(chunk)).toBe(USER_CANCELLED_ABORT_REASON);
  });

  it("returns undefined for non-abort chunks", () => {
    expect(
      getAbortReasonFromChunk({ type: "text-delta", id: "1", delta: "hi" }),
    ).toBeUndefined();
  });

  it("defaults client-side aborts to user_cancelled", () => {
    expect(resolveChatAbortReason({ isAbort: true, streamReason: null })).toBe(
      USER_CANCELLED_ABORT_REASON,
    );
    expect(resolveChatAbortReason({ isAbort: false })).toBeNull();
  });

  it("preserves stream abort reasons when present", () => {
    expect(
      resolveChatAbortReason({ isAbort: true, streamReason: "timeout" }),
    ).toBe("timeout");
  });

  it("describes known and unknown abort reasons", () => {
    expect(describeChatAbortReason(USER_CANCELLED_ABORT_REASON)).toBe(
      "Generation stopped",
    );
    expect(describeChatAbortReason("timeout")).toBe(
      "Generation stopped: timed out",
    );
    expect(describeChatAbortReason("provider_reset")).toBe(
      "Generation stopped: provider_reset",
    );
  });
});
