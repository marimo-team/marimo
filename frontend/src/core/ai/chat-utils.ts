/* Copyright 2024 Marimo. All rights reserved. */
import type { ChatState } from "./state";

export const addMessageToChat = (
  chatState: ChatState,
  chatId: string | null,
  role: "user" | "assistant",
  content: string,
): ChatState => {
  if (!chatId) {
    return chatState;
  }
  return {
    ...chatState,
    chats: chatState.chats.map((chat) =>
      chat.id === chatId
        ? {
            ...chat,
            messages: [
              ...chat.messages,
              {
                role,
                content,
                timestamp: Date.now(),
              },
            ],
            updatedAt: Date.now(),
          }
        : chat,
    ),
  };
};
