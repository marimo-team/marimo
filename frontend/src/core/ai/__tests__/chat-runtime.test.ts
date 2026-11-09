/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it, vi } from "vitest";
import { getChatRuntime } from "../chat-runtime";
import { createChatSession } from "../chat-session";
import { type ChatId, runningChatIdsAtom, unreadChatIdsAtom } from "../state";

const chatId = "same-chat" as ChatId;

describe("chat runtime ownership", () => {
  it("isolates sessions, visibility, and tab status between notebook stores", () => {
    const store = createStore();
    const otherStore = createStore();
    const runtime = getChatRuntime(store);
    const other = getChatRuntime(otherStore);
    const create = vi.fn(() =>
      createChatSession({
        id: chatId,
        store,
        saveMessages: vi.fn(),
        onToolCall: vi.fn(),
      }),
    );
    const session = runtime.getOrCreateSession(chatId, create);
    expect(runtime.getOrCreateSession(chatId, create)).toBe(session);
    expect(create).toHaveBeenCalledOnce();
    runtime.viewChat(chatId);
    runtime.setRunning(chatId, true);
    expect(getChatRuntime(store)).toBe(runtime);
    expect(other.sessions.size).toBe(0);
    expect(other.viewedChatId).toBeNull();
    expect(otherStore.get(runningChatIdsAtom)).toEqual(new Set());
    expect(otherStore.get(unreadChatIdsAtom)).toEqual(new Set());
    runtime.hideChat(chatId);
    expect(runtime.viewedChatId).toBeNull();
    runtime.closeTab(chatId);
  });
});
