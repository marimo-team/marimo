/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Mocks } from "@/__mocks__/common";
import {
  GauthParentBridgeError,
  startGoogleAuthFromParent,
} from "../parent-bridge";
import {
  isMarimoGauthOpenLink,
  isMarimoGauthRequest,
  type MarimoGauthNeedsLinkMessage,
  type MarimoGauthOpenLinkMessage,
  type MarimoGauthRequestMessage,
  type MarimoGauthResultMessage,
  PROTOCOL_VERSION,
} from "../types";

vi.mock("@/utils/Logger", () => ({ Logger: Mocks.quietLogger() }));

/**
 * Test-only assertion: narrows an outgoing message to the concrete
 * `MARIMO_GAUTH_REQUEST` shape using the production type guard. Fails
 * the test if the message is not that shape. No casts at the call
 * site.
 */
function assertIsRequest(
  message: unknown,
): asserts message is MarimoGauthRequestMessage {
  if (!isMarimoGauthRequest(message)) {
    throw new Error(
      `expected MARIMO_GAUTH_REQUEST, got ${JSON.stringify(message)}`,
    );
  }
}

function assertIsOpenLink(
  message: unknown,
): asserts message is MarimoGauthOpenLinkMessage {
  if (!isMarimoGauthOpenLink(message)) {
    throw new Error(
      `expected MARIMO_GAUTH_OPEN_LINK, got ${JSON.stringify(message)}`,
    );
  }
}

describe("startGoogleAuthFromParent", () => {
  let parentPostedMessages: unknown[] = [];
  let mockParent: { postMessage: (msg: unknown, origin: string) => void };

  /**
   * Dispatch a `message` event that the iframe-side handler will
   * accept. We force `event.source === window.parent` because the
   * production handler rejects everything else as a token-injection
   * spoof attempt. Tests must opt into "looks like the parent" via
   * this helper so the security check stays unit-tested rather than
   * silently bypassed.
   */
  function dispatchFromParent(data: unknown): void {
    window.dispatchEvent(
      new MessageEvent("message", {
        data,
        // jsdom's MessageEvent constructor types `source` as
        // `MessageEventSource | null`; our mock parent is a plain
        // object, so cast through `unknown` rather than fabricating a
        // full Window.
        source: window.parent as unknown as Window,
      }),
    );
  }

  beforeEach(() => {
    parentPostedMessages = [];
    mockParent = {
      postMessage: (msg) => {
        parentPostedMessages.push(msg);
      },
    };
    Object.defineProperty(window, "parent", {
      configurable: true,
      value: mockParent,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "parent", {
      configurable: true,
      value: window,
    });
  });

  it("posts a well-formed REQUEST and resolves with the matching RESULT", async () => {
    const handle = startGoogleAuthFromParent({
      requestId: "req-1",
      scopes: ["https://www.googleapis.com/auth/drive"],
    });

    expect(parentPostedMessages).toHaveLength(1);
    const sent = parentPostedMessages[0];
    assertIsRequest(sent);
    expect(sent.request_id).toBe("req-1");
    expect(sent.provider).toBe("google");
    expect(sent.protocol_version).toBe(PROTOCOL_VERSION);
    expect(sent.scopes).toEqual(["https://www.googleapis.com/auth/drive"]);

    const reply: MarimoGauthResultMessage = {
      type: "MARIMO_GAUTH_RESULT",
      protocol_version: PROTOCOL_VERSION,
      request_id: "req-1",
      status: "ok",
      access_token: "ya29.test",
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      scope: "https://www.googleapis.com/auth/drive",
      token_type: "Bearer",
    };
    dispatchFromParent(reply);

    await expect(handle.promise).resolves.toEqual(reply);
  });

  it("fires onNeedsLink with a sendOpenLink that posts the right OPEN_LINK message", () => {
    const onNeedsLink =
      vi.fn<
        (msg: MarimoGauthNeedsLinkMessage, sendOpenLink: () => void) => void
      >();

    startGoogleAuthFromParent({
      requestId: "req-2",
      scopes: ["https://www.googleapis.com/auth/drive"],
      onNeedsLink,
    });

    const needsLink: MarimoGauthNeedsLinkMessage = {
      type: "MARIMO_GAUTH_NEEDS_LINK",
      protocol_version: PROTOCOL_VERSION,
      request_id: "req-2",
      missing_scopes: ["https://www.googleapis.com/auth/drive"],
      additional_scopes: ["https://www.googleapis.com/auth/drive"],
    };
    dispatchFromParent(needsLink);

    expect(onNeedsLink).toHaveBeenCalledTimes(1);
    const [msg, sendOpenLink] = onNeedsLink.mock.calls[0]!;
    expect(msg).toEqual(needsLink);

    // Calling sendOpenLink should synchronously postMessage to parent
    // — synchronous behavior is what preserves user-activation.
    sendOpenLink();
    const openLink = parentPostedMessages.at(-1);
    assertIsOpenLink(openLink);
    expect(openLink.request_id).toBe("req-2");
    expect(openLink.additional_scopes).toEqual([
      "https://www.googleapis.com/auth/drive",
    ]);
  });

  it("does NOT terminate on NEEDS_LINK; still resolves on subsequent RESULT", async () => {
    const onNeedsLink = vi.fn();
    const handle = startGoogleAuthFromParent({
      requestId: "req-3",
      scopes: ["a"],
      onNeedsLink,
    });

    dispatchFromParent({
      type: "MARIMO_GAUTH_NEEDS_LINK",
      protocol_version: PROTOCOL_VERSION,
      request_id: "req-3",
      missing_scopes: ["a"],
      additional_scopes: ["a"],
    });

    // Some time later, parent finishes the popup flow.
    dispatchFromParent({
      type: "MARIMO_GAUTH_RESULT",
      protocol_version: PROTOCOL_VERSION,
      request_id: "req-3",
      status: "ok",
      access_token: "tok",
      expires_at: 0,
      scope: "a",
      token_type: "Bearer",
    });

    await expect(handle.promise).resolves.toMatchObject({
      status: "ok",
      access_token: "tok",
    });
    expect(onNeedsLink).toHaveBeenCalledTimes(1);
  });

  it("ignores messages with a different request_id", async () => {
    const handle = startGoogleAuthFromParent({
      requestId: "req-keep",
      scopes: ["a"],
      timeoutMs: 50,
    });

    dispatchFromParent({
      type: "MARIMO_GAUTH_RESULT",
      protocol_version: PROTOCOL_VERSION,
      request_id: "req-other",
      status: "ok",
      access_token: "wrong",
      expires_at: 0,
      scope: "",
      token_type: "Bearer",
    });

    await expect(handle.promise).rejects.toMatchObject({
      name: "GauthParentBridgeError",
      code: "timeout",
    });
  });

  it("rejects messages whose event.source is not window.parent", async () => {
    const handle = startGoogleAuthFromParent({
      requestId: "req-spoof",
      scopes: ["a"],
      timeoutMs: 50,
    });

    // Forged result message dispatched without a `source` set — i.e.
    // pretending to come from no particular window. The handler must
    // ignore it and time out instead of resolving with the attacker's
    // `access_token`.
    window.dispatchEvent(
      new MessageEvent("message", {
        data: {
          type: "MARIMO_GAUTH_RESULT",
          protocol_version: PROTOCOL_VERSION,
          request_id: "req-spoof",
          status: "ok",
          access_token: "attacker-token",
          expires_at: 0,
          scope: "a",
          token_type: "Bearer",
        },
      }),
    );

    await expect(handle.promise).rejects.toMatchObject({
      name: "GauthParentBridgeError",
      code: "timeout",
    });
  });

  it("rejects with parent_unavailable when there is no parent frame", async () => {
    Object.defineProperty(window, "parent", {
      configurable: true,
      value: window,
    });

    const handle = startGoogleAuthFromParent({
      requestId: "req-x",
      scopes: ["a"],
    });
    await expect(handle.promise).rejects.toBeInstanceOf(GauthParentBridgeError);
    await expect(handle.promise).rejects.toMatchObject({
      code: "parent_unavailable",
    });
  });

  it("cancel() rejects the promise and removes the listener", async () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const handle = startGoogleAuthFromParent({
      requestId: "req-cancel",
      scopes: ["a"],
    });

    handle.cancel();

    await expect(handle.promise).rejects.toMatchObject({
      code: "user_cancelled",
    });
    const removedMessage = removeSpy.mock.calls.some((c) => c[0] === "message");
    expect(removedMessage).toBe(true);
  });
});
