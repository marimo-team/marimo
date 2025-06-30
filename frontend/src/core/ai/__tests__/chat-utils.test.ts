/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { addMessageToChat } from "../chat-utils";
import type { ChatState } from "../state";

describe("addMessageToChat", () => {
  const mockChatState: ChatState = {
    chats: [
      {
        id: "chat-1",
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
        id: "chat-2",
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
    ],
    activeChatId: "chat-1",
  };

  it("should add a new message to an existing chat", () => {
    const result = addMessageToChat(
      mockChatState,
      "chat-1",
      "msg-4",
      "user",
      "New message",
    );

    expect(result.chats).toHaveLength(2);
    const updatedChat = result.chats.find((chat) => chat.id === "chat-1");
    expect(updatedChat?.messages).toHaveLength(3);
    expect(updatedChat?.messages[2]).toEqual({
      id: "msg-4",
      role: "user",
      content: "New message",
      timestamp: expect.any(Number),
    });
    expect(updatedChat?.updatedAt).toBeGreaterThan(
      mockChatState.chats[0].updatedAt,
    );
  });

  it("should update an existing message", () => {
    const result = addMessageToChat(
      mockChatState,
      "chat-1",
      "msg-1",
      "user",
      "Updated content",
    );

    expect(result.chats).toHaveLength(2);
    const updatedChat = result.chats.find((chat) => chat.id === "chat-1");
    expect(updatedChat?.messages).toHaveLength(2);
    expect(updatedChat?.messages[0]).toEqual({
      id: "msg-1",
      role: "user",
      content: "Updated content",
      timestamp: 1000,
    });
    expect(updatedChat?.updatedAt).toBeGreaterThan(
      mockChatState.chats[0].updatedAt,
    );
  });

  it("should handle message parts", () => {
    const parts = [{ type: "text" as const, text: "Part content" }];
    const result = addMessageToChat(
      mockChatState,
      "chat-1",
      "msg-5",
      "assistant",
      "Message with parts",
      parts,
    );

    const updatedChat = result.chats.find((chat) => chat.id === "chat-1");
    expect(updatedChat?.messages[2].parts).toEqual(parts);
  });

  it("should update message parts", () => {
    const originalParts = [{ type: "text" as const, text: "Original" }];
    const updatedParts = [{ type: "text" as const, text: "Updated" }];

    const stateWithParts: ChatState = {
      ...mockChatState,
      chats: [
        {
          ...mockChatState.chats[0],
          messages: [
            {
              ...mockChatState.chats[0].messages[0],
              parts: originalParts,
            },
            mockChatState.chats[0].messages[1],
          ],
        },
        mockChatState.chats[1],
      ],
    };

    const result = addMessageToChat(
      stateWithParts,
      "chat-1",
      "msg-1",
      "user",
      "Updated content",
      updatedParts,
    );

    const updatedChat = result.chats.find((chat) => chat.id === "chat-1");
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
      "non-existent-chat",
      "msg-4",
      "user",
      "New message",
    );

    expect(result).toEqual(mockChatState);
  });

  it("should not modify other chats when updating a specific chat", () => {
    const result = addMessageToChat(
      mockChatState,
      "chat-1",
      "msg-4",
      "user",
      "New message",
    );

    const unchangedChat = result.chats.find((chat) => chat.id === "chat-2");
    expect(unchangedChat).toEqual(mockChatState.chats[1]);
  });

  it("should preserve message order when adding new messages", () => {
    const result = addMessageToChat(
      mockChatState,
      "chat-1",
      "msg-4",
      "user",
      "New message",
    );

    const updatedChat = result.chats.find((chat) => chat.id === "chat-1");
    expect(updatedChat?.messages[0].id).toBe("msg-1");
    expect(updatedChat?.messages[1].id).toBe("msg-2");
    expect(updatedChat?.messages[2].id).toBe("msg-4");
  });

  it("should handle empty chat messages array", () => {
    const emptyChatState: ChatState = {
      chats: [
        {
          id: "empty-chat",
          title: "Empty Chat",
          messages: [],
          createdAt: 1000,
          updatedAt: 1000,
        },
      ],
      activeChatId: "empty-chat",
    };

    const result = addMessageToChat(
      emptyChatState,
      "empty-chat",
      "msg-1",
      "user",
      "First message",
    );

    const updatedChat = result.chats.find((chat) => chat.id === "empty-chat");
    expect(updatedChat?.messages).toHaveLength(1);
    expect(updatedChat?.messages[0].content).toBe("First message");
  });

  it("should handle different message roles", () => {
    const result = addMessageToChat(
      mockChatState,
      "chat-1",
      "msg-4",
      "assistant",
      "Assistant response",
    );

    const updatedChat = result.chats.find((chat) => chat.id === "chat-1");
    expect(updatedChat?.messages[2].role).toBe("assistant");
  });
});
