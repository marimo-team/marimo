/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "@/utils/Logger";
import type { ChatState } from "./state";

export const addMessageToChat = (
  chatState: ChatState,
  chatId: string | null,
  role: "user" | "assistant",
  content: string,
): ChatState => {
  if (!chatId) {
    Logger.warn("No active chat");
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
