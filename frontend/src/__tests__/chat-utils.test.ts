/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import { Maps } from "@/utils/maps";
import { replaceMessagesInChat } from "../core/ai/chat-utils";
import {
  closeChatTab,
  type Chat,
  type ChatId,
  type ChatState,
  MAX_STORED_CHATS,
  openChatTab,
  pruneChats,
} from "../core/ai/state";

const CHAT_1 = "chat-1" as ChatId;
const CHAT_2 = "chat-2" as ChatId;

function makeChat(id: number): Chat {
  return {
    id: `chat-${id}` as ChatId,
    title: `Chat ${id}`,
    messages: [{ id: `m-${id}`, role: "user", parts: [] }],
    createdAt: id,
    updatedAt: id,
  };
}

function asMap(list: Iterable<Chat>) {
  return Maps.keyBy(list, (c) => c.id);
}
describe("replaceMessagesInChat", () => {
  const mockChatState: ChatState = {
    chats: asMap([
      {
        id: CHAT_1,
        title: "Test Chat 1",
        messages: [
          {
            id: "msg-1",
            role: "user",
            parts: [{ type: "text", text: "Hello" }],
            metadata: { timestamp: 1000 },
          },
        ],
        createdAt: 1000,
        updatedAt: 2000,
      },
    ]),
    activeChatId: CHAT_1,
    openChatIds: [CHAT_1],
  };

  it("replaces messages in a chat", () => {
    const newMessages: UIMessage[] = [
      {
        id: "msg-2",
        role: "assistant",
        parts: [{ type: "text", text: "Hi there!" }],
        metadata: { timestamp: 2000 },
      },
    ];
    const result = replaceMessagesInChat({
      chatState: mockChatState,
      chatId: CHAT_1,
      messages: newMessages,
    });
    expect(result.chats.get(CHAT_1)?.messages).toEqual(newMessages);
    expect(result.chats.get(CHAT_1)?.updatedAt).toBeGreaterThan(
      mockChatState.chats.get(CHAT_1)?.updatedAt ?? 0,
    );
  });

  it("returns unchanged state if chatId is null", () => {
    const result = replaceMessagesInChat({
      chatState: mockChatState,
      chatId: null,
      messages: [],
    });
    expect(result).toEqual(mockChatState);
  });
});

describe("openChatTab", () => {
  const baseState: ChatState = {
    chats: asMap([
      {
        id: CHAT_1,
        title: "Chat 1",
        messages: [],
        createdAt: 1000,
        updatedAt: 1000,
      },
      {
        id: CHAT_2,
        title: "Chat 2",
        messages: [],
        createdAt: 2000,
        updatedAt: 2000,
      },
    ]),
    activeChatId: null,
    openChatIds: [],
  };

  it("opens a chat tab and sets it active", () => {
    const result = openChatTab(baseState, CHAT_1);
    expect(result.activeChatId).toBe(CHAT_1);
    expect(result.openChatIds).toEqual([CHAT_1]);
  });

  it("does not duplicate open tabs", () => {
    const state = { ...baseState, openChatIds: [CHAT_1], activeChatId: CHAT_2 };
    const result = openChatTab(state, CHAT_1);
    expect(result.openChatIds).toEqual([CHAT_1]);
    expect(result.activeChatId).toBe(CHAT_1);
  });
});

describe("closeChatTab", () => {
  const baseState: ChatState = {
    chats: asMap([
      {
        id: CHAT_1,
        title: "Chat 1",
        messages: [{ id: "m1", role: "user", parts: [] }],
        createdAt: 1000,
        updatedAt: 1000,
      },
      {
        id: CHAT_2,
        title: "Chat 2",
        messages: [{ id: "m2", role: "user", parts: [] }],
        createdAt: 2000,
        updatedAt: 2000,
      },
    ]),
    activeChatId: CHAT_2,
    openChatIds: [CHAT_1, CHAT_2],
  };

  it("hides a tab without deleting the chat", () => {
    const result = closeChatTab(baseState, CHAT_1);
    expect(result.openChatIds).toEqual([CHAT_2]);
    expect(result.activeChatId).toBe(CHAT_2);
    expect(result.chats.has(CHAT_1)).toBe(true);
  });

  it("activates a neighbor when closing the active tab", () => {
    const result = closeChatTab(baseState, CHAT_2);
    expect(result.openChatIds).toEqual([CHAT_1]);
    expect(result.activeChatId).toBe(CHAT_1);
    expect(result.chats.has(CHAT_2)).toBe(true);
  });

  it("clears active chat when closing the last tab", () => {
    const state = { ...baseState, openChatIds: [CHAT_2], activeChatId: CHAT_2 };
    const result = closeChatTab(state, CHAT_2);
    expect(result.openChatIds).toEqual([]);
    expect(result.activeChatId).toBeNull();
    expect(result.chats.has(CHAT_2)).toBe(true);
  });

  it("returns unchanged state when the tab is not open", () => {
    const state = { ...baseState, openChatIds: [CHAT_2], activeChatId: CHAT_2 };
    const result = closeChatTab(state, CHAT_1);
    expect(result).toBe(state);
  });
});

describe("pruneChats", () => {
  it("returns the same map when under the cap", () => {
    const chats = Maps.keyBy(
      Array.from({ length: 5 }, (_, i) => makeChat(i)),
      (c) => c.id,
    );
    expect(pruneChats(chats, [])).toBe(chats);
  });

  it("keeps the most recently updated chats up to the cap", () => {
    const chats = Maps.keyBy(
      Array.from({ length: MAX_STORED_CHATS + 5 }, (_, i) => makeChat(i)),
      (c) => c.id,
    );
    const result = pruneChats(chats, []);
    expect(result.size).toBe(MAX_STORED_CHATS);
    // The 5 oldest (updatedAt 0..4) should be evicted.
    expect(result.has("chat-0" as ChatId)).toBe(false);
    expect(result.has("chat-4" as ChatId)).toBe(false);
    expect(result.has("chat-5" as ChatId)).toBe(true);
  });

  it("never evicts protected (open) chats, even when old", () => {
    const chats = Maps.keyBy(
      Array.from({ length: MAX_STORED_CHATS + 5 }, (_, i) => makeChat(i)),
      (c) => c.id,
    );
    const oldId = "chat-0" as ChatId;
    const result = pruneChats(chats, [oldId]);
    expect(result.has(oldId)).toBe(true);
    expect(result.size).toBe(MAX_STORED_CHATS + 1);
  });
});
