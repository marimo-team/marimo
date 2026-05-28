/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessageChunk } from "ai";
import { describe, expect, it, vi } from "vitest";
import { routeIncomingChatChunk } from "../chat-ui";

/**
 * The stale-chunk filter prevents chunks from an aborted run from being enqueued into a new run's stream.
 *
 * It triggers when:
 *   1. User sends a prompt (request_id = OLD), kernel starts emitting chunks
 *   2. User clicks Stop — frontend tears down its controller, fires cancel_prompt
 *   3. Kernel hasn't received the cancel yet and is still emitting chunks
 *   4. User sends a new prompt (request_id = NEW), new controller opens
 *   5. Late chunks tagged OLD arrive after NEW's controller is in place
 */

const makeChunk = (opts: {
  messageId: string;
  content: unknown;
  isFinal?: boolean;
}): Parameters<typeof routeIncomingChatChunk>[0] => ({
  type: "stream_chunk",
  message_id: opts.messageId,
  content: opts.content as UIMessageChunk | null,
  is_final: opts.isFinal ?? false,
});

const makeRefs = () => ({
  controllerRef: {
    current: null as ReadableStreamDefaultController<UIMessageChunk> | null,
  },
  activeRequestIdRef: { current: null as string | null },
});

const makeMockController = () => {
  return {
    enqueue: vi.fn(),
    close: vi.fn(),
    error: vi.fn(),
    desiredSize: 0,
  } as unknown as ReadableStreamDefaultController<UIMessageChunk> & {
    enqueue: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  };
};

describe("routeIncomingChatChunk", () => {
  it("drops chunks when there is no active controller", () => {
    const refs = makeRefs();

    const result = routeIncomingChatChunk(
      makeChunk({
        messageId: "req-A",
        content: { type: "text-delta", id: "t1", delta: "hi" },
      }),
      refs,
    );

    expect(result).toBe("dropped-no-controller");
  });

  it("enqueues chunks that match the active request_id", () => {
    const refs = makeRefs();
    const controller = makeMockController();
    refs.controllerRef.current = controller;
    refs.activeRequestIdRef.current = "req-A";

    const chunk = { type: "text-delta", id: "t1", delta: "hi" } as const;
    const result = routeIncomingChatChunk(
      makeChunk({ messageId: "req-A", content: chunk }),
      refs,
    );

    expect(result).toBe("enqueued");
    expect(controller.enqueue).toHaveBeenCalledWith(chunk);
    expect(controller.close).not.toHaveBeenCalled();
  });

  it("closes the controller and clears refs on is_final", () => {
    const refs = makeRefs();
    const controller = makeMockController();
    refs.controllerRef.current = controller;
    refs.activeRequestIdRef.current = "req-A";

    const result = routeIncomingChatChunk(
      makeChunk({ messageId: "req-A", content: null, isFinal: true }),
      refs,
    );

    expect(result).toBe("closed");
    expect(controller.close).toHaveBeenCalledTimes(1);
    expect(refs.controllerRef.current).toBeNull();
    expect(refs.activeRequestIdRef.current).toBeNull();
  });

  it("drops chunks whose message_id does not match the active run", () => {
    // Simulates the bug: kernel hasn't received cancel for OLD yet but the
    // user has already started a NEW run. A reasoning-delta for OLD arrives
    // here; it must not be enqueued into NEW's stream.
    const refs = makeRefs();
    const controller = makeMockController();
    refs.controllerRef.current = controller;
    refs.activeRequestIdRef.current = "req-NEW";

    const staleChunk = {
      type: "reasoning-delta",
      id: "r-old",
      delta: "...",
    } as const;
    const result = routeIncomingChatChunk(
      makeChunk({ messageId: "req-OLD", content: staleChunk }),
      refs,
    );

    expect(result).toBe("dropped-stale");
    expect(controller.enqueue).not.toHaveBeenCalled();
    expect(controller.close).not.toHaveBeenCalled();
    expect(refs.activeRequestIdRef.current).toBe("req-NEW");
  });

  it("drops is_final from a stale run without closing the active stream", () => {
    // Belt-and-suspenders: an `is_final` for OLD that races in after NEW
    // started must not tear down NEW's controller.
    const refs = makeRefs();
    const controller = makeMockController();
    refs.controllerRef.current = controller;
    refs.activeRequestIdRef.current = "req-NEW";

    const result = routeIncomingChatChunk(
      makeChunk({ messageId: "req-OLD", content: null, isFinal: true }),
      refs,
    );

    expect(result).toBe("dropped-stale");
    expect(controller.close).not.toHaveBeenCalled();
    expect(refs.controllerRef.current).toBe(controller);
    expect(refs.activeRequestIdRef.current).toBe("req-NEW");
  });

  it("forwards reasoning-start/delta/end sequences when ids match", () => {
    // Walks the canonical happy path for a reasoning stream end-to-end.
    const refs = makeRefs();
    const controller = makeMockController();
    refs.controllerRef.current = controller;
    refs.activeRequestIdRef.current = "req-A";

    const sequence = [
      { type: "reasoning-start", id: "r1" },
      { type: "reasoning-delta", id: "r1", delta: "thinking" },
      { type: "reasoning-end", id: "r1" },
    ] as const;
    for (const chunk of sequence) {
      const result = routeIncomingChatChunk(
        makeChunk({ messageId: "req-A", content: chunk }),
        refs,
      );
      expect(result).toBe("enqueued");
    }

    expect(controller.enqueue).toHaveBeenCalledTimes(3);
    expect(controller.enqueue).toHaveBeenNthCalledWith(1, sequence[0]);
    expect(controller.enqueue).toHaveBeenNthCalledWith(2, sequence[1]);
    expect(controller.enqueue).toHaveBeenNthCalledWith(3, sequence[2]);
  });

  it(
    "drops stale reasoning-delta after Stop → new run sequence " +
      "(regression for missing reasoning part error)",
    () => {
      // Full scenario: A runs, A is stopped, B starts, A's late chunk arrives.
      const refs = makeRefs();

      // 1. Run A starts: controller A active.
      const controllerA = makeMockController();
      refs.controllerRef.current = controllerA;
      refs.activeRequestIdRef.current = "req-A";

      // First reasoning chunks for A flow through.
      routeIncomingChatChunk(
        makeChunk({
          messageId: "req-A",
          content: { type: "reasoning-start", id: "rA" },
        }),
        refs,
      );
      routeIncomingChatChunk(
        makeChunk({
          messageId: "req-A",
          content: {
            type: "reasoning-delta",
            id: "rA",
            delta: "thinking",
          },
        }),
        refs,
      );
      expect(controllerA.enqueue).toHaveBeenCalledTimes(2);

      // 2. User clicks Stop: abort handler clears refs (simulated).
      refs.controllerRef.current = null;
      refs.activeRequestIdRef.current = null;

      // A late chunk for A arrives in this window — must be a no-op.
      const between = routeIncomingChatChunk(
        makeChunk({
          messageId: "req-A",
          content: {
            type: "reasoning-delta",
            id: "rA",
            delta: "leftover",
          },
        }),
        refs,
      );
      expect(between).toBe("dropped-no-controller");

      // 3. User sends Run B: new controller, new active id.
      const controllerB = makeMockController();
      refs.controllerRef.current = controllerB;
      refs.activeRequestIdRef.current = "req-B";

      // 4. Another late chunk for A arrives AFTER B opened. This is the
      // case that previously threw `Received reasoning-delta for missing
      // reasoning part with ID "rA"` in the SDK parser.
      const stale = routeIncomingChatChunk(
        makeChunk({
          messageId: "req-A",
          content: {
            type: "reasoning-delta",
            id: "rA",
            delta: "still leaking",
          },
        }),
        refs,
      );
      expect(stale).toBe("dropped-stale");
      expect(controllerB.enqueue).not.toHaveBeenCalled();

      // 5. B's own chunks flow normally.
      routeIncomingChatChunk(
        makeChunk({
          messageId: "req-B",
          content: { type: "reasoning-start", id: "rB" },
        }),
        refs,
      );
      routeIncomingChatChunk(
        makeChunk({
          messageId: "req-B",
          content: { type: "reasoning-delta", id: "rB", delta: "fresh" },
        }),
        refs,
      );
      expect(controllerB.enqueue).toHaveBeenCalledTimes(2);
    },
  );

  it("enqueues content alongside is_final and then closes", () => {
    // Sanity: a single chunk that carries both `content` and `is_final` (rare
    // but legal — backend may bundle final content with the terminator)
    // should enqueue then close.
    const refs = makeRefs();
    const controller = makeMockController();
    refs.controllerRef.current = controller;
    refs.activeRequestIdRef.current = "req-A";

    const chunk = { type: "text-delta", id: "t1", delta: "bye" } as const;
    const result = routeIncomingChatChunk(
      makeChunk({ messageId: "req-A", content: chunk, isFinal: true }),
      refs,
    );

    expect(result).toBe("closed");
    expect(controller.enqueue).toHaveBeenCalledWith(chunk);
    expect(controller.close).toHaveBeenCalledTimes(1);
  });
});
