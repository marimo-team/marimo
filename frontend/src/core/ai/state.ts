/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { CellId } from "../cells/ids";

export const aiCompletionCellAtom = atom<{
  cellId: CellId;
  initialPrompt?: string;
} | null>(null);
export const includeOtherCellsAtom = atom<boolean>(false);

export interface Message {
  role: "user" | "assistant" | "data" | "system";
  content: string;
  timestamp: number;
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

export const chatStateAtom = atom<ChatState>({
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
