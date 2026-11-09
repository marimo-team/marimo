/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import type { ChatTransport, UIMessage } from "ai";
import { describe, expect, it, vi } from "vitest";
import { getChatRuntime } from "../chat-runtime";
import { type ChatId, runningChatIdsAtom, unreadChatIdsAtom } from "../state";

const chatId = "same-chat" as ChatId;

describe("chat runtime ownership", () => {
  it("wires session requests and running status to its own store and chat id", async () => {
    const store = createStore();
    const runtime = getChatRuntime(store);
    const sendMessages = vi.fn<ChatTransport<UIMessage>["sendMessages"]>(
      async () =>
        new ReadableStream({
          start(controller) {
            controller.close();
          },
        }),
    );
    const session = runtime.getOrCreateSession(chatId, () => ({
      saveMessages: vi.fn(),
      onToolCall: vi.fn(),
      transport: { sendMessages, reconnectToStream: async () => null },
    }));
    const request = session.sendMessage({
      role: "user",
      parts: [{ type: "text", text: "Hello" }],
    });
    expect(store.get(runningChatIdsAtom)).toEqual(new Set([chatId]));
    await request;
    expect(sendMessages.mock.lastCall?.[0].chatId).toBe(chatId);
    expect(store.get(runningChatIdsAtom)).toEqual(new Set());
    expect(session.store).toBe(store);
  });

  it("isolates sessions, visibility, and tab status between notebook stores", () => {
    const store = createStore();
    const otherStore = createStore();
    const runtime = getChatRuntime(store);
    const other = getChatRuntime(otherStore);
    const create = vi.fn(() => ({
      saveMessages: vi.fn(),
      onToolCall: vi.fn(),
    }));
    const session = runtime.getOrCreateSession(chatId, create);
    expect(runtime.getOrCreateSession(chatId, create)).toBe(session);
    expect(create).toHaveBeenCalledOnce();
    expect(session.controller.id).toBe(chatId);
    expect(session.store).toBe(store);
    runtime.viewChat(chatId);
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
