/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import type { CellId } from "../cells/ids";
import type { Message as AIMessage } from "@ai-sdk/react";

const KEY = "marimo:ai:chatState:v1";

export const aiCompletionCellAtom = atom<{
  cellId: CellId;
  initialPrompt?: string;
} | null>(null);
export const includeOtherCellsAtom = atom<boolean>(false);

export interface Message {
  role: "user" | "assistant" | "data" | "system";
  content: string;
  timestamp: number;
  parts?: AIMessage["parts"];
}

export interface Chat {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface ChatState {
  chats: Chat[];
  activeChatId: string | null;
}

export const chatStateAtom = atomWithStorage<ChatState>(KEY, {
  chats: [],
  activeChatId: null,
});

export const activeChatAtom = atom(
  (get) => {
    const state = get(chatStateAtom);
    return state.chats.find((chat) => chat.id === state.activeChatId);
  },
  (get, set, chatId: string | null) => {
    set(chatStateAtom, (prev) => ({
      ...prev,
      activeChatId: chatId,
    }));
  },
);
