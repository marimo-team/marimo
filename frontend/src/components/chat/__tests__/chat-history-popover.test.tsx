/* Copyright 2026 Marimo. All rights reserved. */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import { TooltipProvider } from "@/components/ui/tooltip";
import { type Chat, type ChatId, chatStateAtom } from "@/core/ai/state";
import { ChatHistoryPopover } from "../chat-history-popover";

const activeId = "active" as ChatId;
const olderId = "older" as ChatId;

function chat(id: ChatId): Chat {
  return {
    id,
    title: `${id} conversation`,
    messages: [
      {
        id: `${id}-message`,
        role: "user",
        parts: [{ type: "text", text: "Hello" }],
      },
    ],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}

function setup(isLoading = false) {
  const store = createStore();
  const setActiveChat = vi.fn();
  const onDeleteChats = vi.fn();

  render(
    <Provider store={store}>
      <ModalProvider>
        <TooltipProvider>
          <ChatHistoryPopover
            activeChatId={activeId}
            setActiveChat={setActiveChat}
            onDeleteChats={onDeleteChats}
            isLoading={isLoading}
          />
        </TooltipProvider>
      </ModalProvider>
    </Provider>,
  );
  act(() =>
    store.set(chatStateAtom, {
      chats: new Map([
        [activeId, chat(activeId)],
        [olderId, chat(olderId)],
      ]),
      activeChatId: activeId,
    }),
  );

  fireEvent.click(screen.getByRole("button", { name: "Previous chats" }));
  return { store, setActiveChat, onDeleteChats };
}

describe("chat history management", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("deletes individual chats immediately without selecting them or closing history", () => {
    const { setActiveChat, onDeleteChats } = setup();
    fireEvent.click(
      screen.getByRole("button", { name: "Delete chat: older conversation" }),
    );
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search chat history...")).toBeVisible();
    expect(onDeleteChats).toHaveBeenCalledExactlyOnceWith(olderId);
    expect(setActiveChat).not.toHaveBeenCalled();
  });

  it("deletes all chats only after confirmation", () => {
    const { onDeleteChats } = setup();
    fireEvent.change(screen.getByPlaceholderText("Search chat history..."), {
      target: { value: "older" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Delete all chats" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("all notebooks");
    expect(onDeleteChats).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete all chats" }));
    expect(onDeleteChats).toHaveBeenCalledExactlyOnceWith(null);
  });

  it("prevents deleting a streaming chat while allowing cleanup of other chats", () => {
    setup(true);
    expect(
      screen.getByRole("button", { name: "Delete chat: active conversation" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Delete all chats" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Delete chat: older conversation" }),
    ).toBeEnabled();
  });

  it("warns above 100 chats and clears the warning after cleanup", () => {
    const { store } = setup();
    const chats = new Map<ChatId, Chat>(
      Array.from({ length: 101 }, (_, index) => {
        const id = `chat-${index}` as ChatId;
        return [id, chat(id)];
      }),
    );
    act(() => store.set(chatStateAtom, { chats, activeChatId: null }));
    const warning = screen.getByText(
      /Delete old chats to free up browser storage/,
    );
    expect(warning).toBeVisible();
    expect(warning).toHaveTextContent(
      "You have over 100 chats. Delete old chats to free up browser storage.",
    );

    act(() =>
      store.set(chatStateAtom, (prev) => ({
        ...prev,
        chats: new Map([...prev.chats].slice(1)),
      })),
    );
    expect(
      screen.queryByText(/Delete old chats to free up browser storage/),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Chats are shared across notebooks."),
    ).toBeVisible();
  });
});
