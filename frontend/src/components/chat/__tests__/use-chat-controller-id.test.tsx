/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ChatId } from "@/core/ai/state";
import { useChatControllerId } from "../use-chat-controller-id";

describe("useChatControllerId", () => {
  it("creates a new ID when starting another unsaved chat", () => {
    const activeChatId = "existing-chat" as ChatId;
    const initialProps: { activeId: ChatId | undefined } = {
      activeId: activeChatId,
    };
    const { result, rerender } = renderHook(
      ({ activeId }: { activeId: ChatId | undefined }) =>
        useChatControllerId(activeId),
      { initialProps },
    );

    expect(result.current.chatControllerId).toBe(activeChatId);

    act(() => result.current.renewDraftChatId());
    rerender({ activeId: undefined });

    expect(result.current.chatControllerId).not.toBe(activeChatId);
  });

  it("renews the ID when the current chat is already unsaved", () => {
    const { result } = renderHook(() => useChatControllerId(undefined));
    const initialDraftId = result.current.chatControllerId;

    act(() => result.current.renewDraftChatId());

    expect(result.current.chatControllerId).not.toBe(initialDraftId);
  });
});
