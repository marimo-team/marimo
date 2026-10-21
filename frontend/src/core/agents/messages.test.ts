/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { StableSessionId } from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { HTTPError } from "@/utils/errors";
import { sendAgentMessage, SendOutcomeUnknownError } from "./messages";

vi.mock("@/core/network/api", () => ({ API: { post: vi.fn() } }));
const SESSION = "session" as StableSessionId;

describe("agent messages", () => {
  beforeEach(() => vi.resetAllMocks());

  it.each([
    undefined,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    { value: undefined },
    new Set([1]),
  ])("rejects unsupported content before dispatch: %j", async (message) => {
    await expect(
      sendAgentMessage(SESSION, message, { to: "agent" }),
    ).rejects.toThrow(/Invalid|Expected/);
    expect(API.post).not.toHaveBeenCalled();
  });

  it.each([
    "",
    null,
    { recipients: [] },
    { recipients: [{ agent_id: "a", status: "delivered" }] },
  ])("treats malformed overall replies as unknown: %j", async (reply) => {
    vi.mocked(API.post).mockResolvedValue(reply);
    await expect(
      sendAgentMessage(SESSION, null, { to: "agent" }),
    ).rejects.toBeInstanceOf(SendOutcomeUnknownError);
    expect(API.post).toHaveBeenCalledOnce();
  });

  it.each([400, 401, 403, 404, 405, 409, 503])(
    "retains definite pre-dispatch failures (%s)",
    async (status) => {
      const error = new HTTPError(status, "Unavailable", {
        code: "unavailable",
        detail: "Unavailable",
      });
      vi.mocked(API.post).mockRejectedValue(error);
      await expect(
        sendAgentMessage(SESSION, null, { broadcast: true }),
      ).rejects.toBe(error);
      expect(API.post).toHaveBeenCalledOnce();
    },
  );

  it.each([400, 409, 500, 503])(
    "preserves uncertainty for an untyped HTTP failure (%s)",
    async (status) => {
      vi.mocked(API.post).mockRejectedValue(
        new HTTPError(status, "No result", { detail: "An upstream failed" }),
      );
      await expect(
        sendAgentMessage(SESSION, null, { to: "agent" }),
      ).rejects.toBeInstanceOf(SendOutcomeUnknownError);
      expect(API.post).toHaveBeenCalledOnce();
    },
  );

  it("preserves the server's per-recipient outcomes and bounds the HTTP wait", async () => {
    const reply = {
      recipients: [{ agent_id: "a", status: "unknown", detail: "No receipt" }],
    };
    vi.mocked(API.post).mockResolvedValue(reply);
    await expect(
      sendAgentMessage(SESSION, [null, true, "λ"], { to: "a" }),
    ).resolves.toEqual(reply);
    expect(API.post).toHaveBeenCalledWith(
      "/pair/notebooks/session/messages",
      { message: [null, true, "λ"], to: "a" },
      { signal: expect.any(AbortSignal) },
    );
  });
});
