/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "@/utils/Logger";
import type { ChatState } from "./state";
import type { Message as AIMessage } from "@ai-sdk/react";

export const addMessageToChat = (
  chatState: ChatState,
  chatId: string | null,
  role: "user" | "assistant",
  content: string,
  parts?: AIMessage["parts"],
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
                parts,
              },
            ],
            updatedAt: Date.now(),
          }
        : chat,
    ),
  };
};
