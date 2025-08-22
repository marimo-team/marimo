/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { Maps } from "@/utils/maps";
import { addMessageToChat } from "../core/ai/chat-utils";
import type { Chat, ChatId, ChatState } from "../core/ai/state";

const CHAT_1 = "chat-1" as ChatId;
const CHAT_2 = "chat-2" as ChatId;

function first(map: Map<ChatId, Chat>) {
  return [...map.values()][0];
}

function asMap(list: Iterable<Chat>) {
  return Maps.keyBy(list, (c) => c.id);
}

describe("addMessageToChat", () => {
  const mockChatState: ChatState = {
    chats: asMap([
      {
        id: CHAT_1,
        title: "Test Chat 1",
        messages: [
          {
            id: "msg-1",
            role: "user",
            content: "Hello",
            timestamp: 1000,
          },
          {
            id: "msg-2",
            role: "assistant",
            content: "Hi there!",
            timestamp: 2000,
          },
        ],
        createdAt: 1000,
        updatedAt: 2000,
      },
      {
        id: CHAT_2,
        title: "Test Chat 2",
        messages: [
          {
            id: "msg-3",
            role: "user",
            content: "How are you?",
            timestamp: 3000,
          },
        ],
        createdAt: 3000,
        updatedAt: 3000,
      },
    ]),
    activeChatId: CHAT_1,
  };

  it("should add a new message to an existing chat", () => {
    const result = addMessageToChat(
      mockChatState,
      CHAT_1,
      "msg-4",
      "user",
      "New message",
    );

    expect(result.chats).toHaveLength(2);
    const updatedChat = result.chats.get(CHAT_1);
    expect(updatedChat?.messages).toHaveLength(3);
    expect(updatedChat?.messages[2]).toEqual({
      id: "msg-4",
      role: "user",
      content: "New message",
      timestamp: expect.any(Number),
    });
    expect(updatedChat?.updatedAt).toBeGreaterThan(
      first(mockChatState.chats).updatedAt,
    );
  });

  it("should update an existing message", () => {
    const result = addMessageToChat(
      mockChatState,
      CHAT_1,
      "msg-1",
      "user",
      "Updated content",
    );

    expect(result.chats).toHaveLength(2);
    const updatedChat = result.chats.get(CHAT_1);
    expect(updatedChat?.messages).toHaveLength(2);
    expect(updatedChat?.messages[0]).toEqual({
      id: "msg-1",
      role: "user",
      content: "Updated content",
      timestamp: 1000,
    });
    expect(updatedChat?.updatedAt).toBeGreaterThan(
      first(mockChatState.chats).updatedAt,
    );
  });

  it("should handle message parts", () => {
    const parts = [{ type: "text" as const, text: "Part content" }];
    const result = addMessageToChat(
      mockChatState,
      CHAT_1,
      "msg-5",
      "assistant",
      "Message with parts",
      parts,
    );

    const updatedChat = result.chats.get(CHAT_1);
    expect(updatedChat?.messages[2].parts).toEqual(parts);
  });

  it("should update message parts", () => {
    const originalParts = [{ type: "text" as const, text: "Original" }];
    const updatedParts = [{ type: "text" as const, text: "Updated" }];
    const chats = [...mockChatState.chats.values()];

    const stateWithParts: ChatState = {
      ...mockChatState,
      chats: asMap([
        {
          ...chats[0],
          messages: [
            {
              ...chats[0].messages[0],
              parts: originalParts,
            },
            chats[0].messages[1],
          ],
        },
        chats[1],
      ]),
    };

    const result = addMessageToChat(
      stateWithParts,
      CHAT_1,
      "msg-1",
      "user",
      "Updated content",
      updatedParts,
    );

    const updatedChat = result.chats.get(CHAT_1);
    expect(updatedChat?.messages[0].parts).toEqual(updatedParts);
  });

  it("should return unchanged state when chatId is null", () => {
    const result = addMessageToChat(
      mockChatState,
      null,
      "msg-4",
      "user",
      "New message",
    );

    expect(result).toEqual(mockChatState);
  });

  it("should return unchanged state when chatId does not exist", () => {
    const result = addMessageToChat(
      mockChatState,
      "non-existent-chat" as ChatId,
      "msg-4",
      "user",
      "New message",
    );

    expect(result).toEqual(mockChatState);
  });

  it("should not modify other chats when updating a specific chat", () => {
    const result = addMessageToChat(
      mockChatState,
      CHAT_1,
      "msg-4",
      "user",
      "New message",
    );

    const unchangedChat = result.chats.get(CHAT_2);
    expect(unchangedChat).toEqual(first(mockChatState.chats));
  });

  it("should preserve message order when adding new messages", () => {
    const result = addMessageToChat(
      mockChatState,
      CHAT_1,
      "msg-4",
      "user",
      "New message",
    );

    const updatedChat = result.chats.get(CHAT_1);
    expect(updatedChat?.messages[0].id).toBe("msg-1");
    expect(updatedChat?.messages[1].id).toBe("msg-2");
    expect(updatedChat?.messages[2].id).toBe("msg-4");
  });

  it("should handle empty chat messages array", () => {
    const chatId = "empty-chat" as ChatId;
    const emptyChatState: ChatState = {
      chats: asMap([
        {
          id: chatId,
          title: "Empty Chat",
          messages: [],
          createdAt: 1000,
          updatedAt: 1000,
        },
      ]),
      activeChatId: chatId,
    };

    const result = addMessageToChat(
      emptyChatState,
      chatId,
      "msg-1",
      "user",
      "First message",
    );

    const updatedChat = result.chats.get(chatId);
    expect(updatedChat?.messages).toHaveLength(1);
    expect(updatedChat?.messages[0].content).toBe("First message");
  });

  it("should handle different message roles", () => {
    const result = addMessageToChat(
      mockChatState,
      CHAT_1,
      "msg-4",
      "assistant",
      "Assistant response",
    );

    const updatedChat = result.chats.get(CHAT_1);
    expect(updatedChat?.messages[2].role).toBe("assistant");
  });
});
