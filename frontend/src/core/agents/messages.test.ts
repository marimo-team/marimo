/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { StableSessionId } from "@/core/kernel/session";
import { API } from "@/core/network/api";
import { HTTPError } from "@/utils/errors";
import { sendAgentMessage, SendOutcomeUnknownError } from "./messages";

vi.mock("@/core/network/api", () => ({ API: { post: vi.fn() } }));
const SESSION = "session" as StableSessionId;

function mockTimeoutClock(reason: unknown) {
  const controller = new AbortController();
  const timeout = vi.spyOn(AbortSignal, "timeout").mockImplementation((ms) => {
    setTimeout(() => controller.abort(reason), ms);
    return controller.signal;
  });
  return { controller, timeout };
}

describe("agent messages", () => {
  beforeEach(() => vi.resetAllMocks());
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

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

  it("preserves the server's per-recipient outcomes", async () => {
    const reply = {
      recipients: [{ agent_id: "a", status: "unknown", detail: "No receipt" }],
    };
    vi.mocked(API.post).mockResolvedValue(reply);
    await expect(
      sendAgentMessage(SESSION, [null, true, "λ"], { to: "a" }),
    ).resolves.toEqual(reply);
    expect(API.post).toHaveBeenCalledWith(
      "/pair/notebooks/session/messages",
      { message: [null, true, "λ"], to: "a", timeout: 30 },
      { signal: expect.any(AbortSignal) },
    );
  });
  it("aborts a pending request after the server wait and retains the cause", async () => {
    vi.useFakeTimers();
    const cause = new Error("Request expired");
    const { controller, timeout } = mockTimeoutClock(cause);
    vi.mocked(API.post).mockImplementation(
      (_url, _body, opts) =>
        new Promise((_resolve, reject) => {
          opts?.signal?.addEventListener("abort", () =>
            reject(opts.signal?.reason),
          );
        }),
    );
    const result = sendAgentMessage(SESSION, null, { to: "agent" }).catch(
      (error: unknown) => error,
    );
    const body = vi.mocked(API.post).mock.calls[0][1] as { timeout: number };
    const clientWait = timeout.mock.calls[0][0];
    expect(clientWait).toBeGreaterThan(body.timeout * 1000);
    await vi.advanceTimersByTimeAsync(body.timeout * 1000);
    expect(controller.signal.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(clientWait - body.timeout * 1000);
    expect(controller.signal.aborted).toBe(true);
    expect(await result).toBeInstanceOf(SendOutcomeUnknownError);
    expect(await result).toMatchObject({ cause });
    expect(API.post).toHaveBeenCalledOnce();
  });

  it("keeps confirmed recipients when the server returns a partial timeout", async () => {
    vi.useFakeTimers();
    mockTimeoutClock(new Error("Request expired"));
    const reply = {
      recipients: [
        { agent_id: "a", status: "submitted", detail: null },
        { agent_id: "b", status: "unknown", detail: "No receipt" },
      ],
    };
    vi.mocked(API.post).mockImplementation(
      (_url, body, opts) =>
        new Promise((resolve, reject) => {
          const wait = (body as { timeout: number }).timeout;
          setTimeout(() => resolve(reply), wait * 1000);
          opts?.signal?.addEventListener("abort", () =>
            reject(opts.signal?.reason),
          );
        }),
    );
    const result = sendAgentMessage(SESSION, null, { broadcast: true }).then(
      (value) => ({ value }),
      (error: unknown) => ({ error }),
    );
    await vi.advanceTimersByTimeAsync(30_000);
    expect(await result).toEqual({ value: reply });
  });
});
