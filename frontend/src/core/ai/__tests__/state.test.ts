/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "@/components/ui/use-toast";
import { type Chat, type ChatId, chatStateAtom } from "../state";

vi.mock("@/components/ui/use-toast", () => ({ toast: vi.fn() }));

const KEY = "marimo:ai:chatState:v5";
const chatId = "saved-chat" as ChatId;
const chat: Chat = {
  id: chatId,
  title: "Saved conversation",
  messages: [
    { id: "message", role: "user", parts: [{ type: "text", text: "Hello" }] },
  ],
  createdAt: 1,
  updatedAt: 1,
};

const unsubscribers: (() => void)[] = [];

function loadStore() {
  const store = createStore();
  unsubscribers.push(store.sub(chatStateAtom, vi.fn()));
  return store;
}

function fillStorage() {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Storage is full", "QuotaExceededError");
  });
}

describe("chat history storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem(
      KEY,
      JSON.stringify({
        chats: [[chatId, chat]],
        activeChatId: chatId,
      }),
    );
  });

  afterEach(() => {
    for (const unsubscribe of unsubscribers.splice(0)) {
      unsubscribe();
    }
    vi.restoreAllMocks();
  });

  it("loads saved history when storage is full", () => {
    fillStorage();
    expect(loadStore().get(chatStateAtom)).toEqual({
      chats: new Map([[chatId, chat]]),
      activeChatId: chatId,
    });
  });

  it("warns on save failure without interrupting in-memory updates", () => {
    const store = loadStore();
    const savedHistory = window.localStorage.getItem(KEY);
    fillStorage();
    const updatedChat = { ...chat, title: "Unsaved conversation" };
    expect(() =>
      store.set(chatStateAtom, {
        chats: new Map([[chatId, updatedChat]]),
        activeChatId: chatId,
      }),
    ).not.toThrow();

    expect(store.get(chatStateAtom).chats.get(chatId)).toEqual(updatedChat);
    expect(window.localStorage.getItem(KEY)).toBe(savedHistory);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "chat-storage-error",
        once: true,
        title: "Chat history couldn't be saved",
      }),
    );
  });

  it("frees storage when history is cleared even if further writes fail", () => {
    window.localStorage.setItem("unrelated-setting", "keep");
    const store = loadStore();
    fillStorage();
    store.set(chatStateAtom, { chats: new Map(), activeChatId: null });

    expect(window.localStorage.getItem(KEY)).toBeNull();
    expect(window.localStorage.getItem("unrelated-setting")).toBe("keep");
    expect(loadStore().get(chatStateAtom)).toEqual({
      chats: new Map(),
      activeChatId: null,
    });
    expect(toast).not.toHaveBeenCalled();
  });
});
