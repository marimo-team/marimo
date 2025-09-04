/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { describe, expect, it } from "vitest";
import { Maps } from "@/utils/maps";
import { replaceMessagesInChat } from "../core/ai/chat-utils";
import type { Chat, ChatId, ChatState } from "../core/ai/state";

const CHAT_1 = "chat-1" as ChatId;

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
