/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  renderHook,
  screen,
} from "@testing-library/react";
import {
  createUIMessageStreamResponse,
  type UIMessage,
  type UIMessageChunk,
} from "ai";
import { createStore, Provider, useAtomValue } from "jotai";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getChatRuntime } from "@/core/ai/chat-runtime";
import { runningChatIdsAtom, unreadChatIdsAtom } from "@/core/ai/state";
import {
  activeChatAtom,
  addChatAndOpenTab,
  type Chat,
  type ChatId,
  chatStateAtom,
  chatGenerationInProgressAtom,
} from "@/core/ai/state";
import { ChatTabs } from "../chat-tabs";
import { LazyActivity } from "@/components/utils/lazy-mount";
import { useChatSession } from "../use-chat-session";

vi.mock("@/core/network/requests", () => ({
  useRequestClient: () => ({ invokeAiTool: vi.fn(), sendRun: vi.fn() }),
}));
vi.mock("@/core/runtime/config", () => ({
  useRuntimeManager: () => ({
    getAiURL: () => new URL("http://localhost/api/ai/chat"),
    headers: () => ({}),
  }),
}));
vi.mock("@/core/cells/actions", () => ({
  useCellActions: () => ({ createCell: vi.fn() }),
}));
vi.mock("@/core/ai/staged-cells", () => ({
  useStagedAICellsActions: () => ({ addStagedCell: vi.fn() }),
}));
vi.mock("@/core/codemirror/copilot/getCodes", () => ({ getCodes: () => "" }));
vi.mock("@/core/ai/tools/registry", () => ({
  FRONTEND_TOOL_REGISTRY: { getToolSchemas: () => [], has: () => false },
}));
vi.mock("../chat-utils", () => ({ handleToolCall: vi.fn() }));
vi.mock("@/core/ai/tool-state", () => ({
  hasPendingToolCalls: () => false,
  hasUnresolvedToolCalls: () => false,
  willAutoContinue: () => false,
  shouldFlushQueue: () => false,
}));

function makeChat(id: string): Chat {
  return {
    id: id as ChatId,
    title: id,
    messages: [],
    createdAt: 0,
    updatedAt: 0,
  };
}

function mockChatResponse() {
  let stream: ReadableStreamDefaultController<UIMessageChunk> | undefined;
  const response = createUIMessageStreamResponse({
    stream: new ReadableStream<UIMessageChunk>({
      start(controller) {
        stream = controller;
      },
    }),
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
  return (text: string, end?: UIMessageChunk) => {
    if (!stream) {
      throw new Error("Expected a response stream");
    }
    for (const chunk of [
      { type: "start", messageId: "reply" },
      { type: "text-start", id: "text" },
      { type: "text-delta", id: "text", delta: text },
      { type: "text-end", id: "text" },
      end ?? { type: "finish" },
    ] satisfies UIMessageChunk[]) {
      stream.enqueue(chunk);
    }
    stream.close();
  };
}

function setup(chats: Chat[] = []) {
  const store = createStore();
  const wrapper = ({ children }: PropsWithChildren) => (
    <Provider store={store}>{children}</Provider>
  );
  const hook = renderHook(() => useChatSession(useAtomValue(activeChatAtom)), {
    wrapper,
  });
  act(() => {
    store.set(chatStateAtom, {
      chats: new Map(chats.map((chat) => [chat.id, chat])),
      activeChatId: chats[0]?.id ?? null,
      openChatIds: chats.map((chat) => chat.id),
    });
  });
  return { store, wrapper, ...hook };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useChatSession", () => {
  it("releases abandoned drafts when opening history chats", () => {
    const { result, store } = setup();
    const draftId = result.current.id;
    const draft = getChatRuntime(store).sessions.get(draftId);
    if (!draft) {
      throw new Error("Expected a draft session");
    }
    const close = vi.spyOn(draft, "close");
    const saved = makeChat("Saved chat");
    act(() =>
      store.set(chatStateAtom, (state) => addChatAndOpenTab(state, saved)),
    );
    expect(close).toHaveBeenCalledExactlyOnceWith({ discard: true });
    expect([...getChatRuntime(store).sessions.keys()]).toEqual([saved.id]);
  });

  it("selects a neighboring tab when deleting the active chat", () => {
    const chatA = makeChat("Chat A");
    const chatB = makeChat("Chat B");
    const { result, store } = setup([chatA, chatB]);
    act(() => {
      expect(getChatRuntime(store).deleteChats(chatA.id)).toBe(true);
    });
    expect(result.current.id).toBe(chatB.id);
    expect(store.get(chatStateAtom)).toEqual({
      chats: new Map([[chatB.id, chatB]]),
      activeChatId: chatB.id,
      openChatIds: [chatB.id],
    });
  });

  it("keeps a draft controller through promotion and creates a fresh draft afterward", () => {
    const { result, rerender, store } = setup();
    const draftId = result.current.id;
    const draftSession = getChatRuntime(store).sessions.get(draftId);
    rerender();
    expect(result.current.id).toBe(draftId);
    expect(getChatRuntime(store).sessions.get(draftId)).toBe(draftSession);

    act(() => {
      store.set(chatStateAtom, (state) =>
        addChatAndOpenTab(state, { ...makeChat(draftId), id: draftId }),
      );
      result.current.renewDraftChatId();
    });
    expect(result.current.id).toBe(draftId);
    expect(getChatRuntime(store).sessions.get(draftId)).toBe(draftSession);

    act(() => {
      store.set(activeChatAtom, null);
    });
    expect(result.current.id).not.toBe(draftId);
    expect(result.current.messages).toEqual([]);
  });

  it("saves a response to its originating chat after selecting another chat", async () => {
    const finishResponse = mockChatResponse();
    const chatA = makeChat("Chat A");
    const chatB = makeChat("Chat B");
    const { result, store, wrapper } = setup([chatA, chatB]);
    render(<ChatTabs />, { wrapper });
    const sessionA = getChatRuntime(store).sessions.get(chatA.id);
    let request: Promise<void>;
    act(() => {
      request = result.current.sendMessage({
        role: "user",
        parts: [{ type: "text", text: "Hello" }],
      });
      store.set(activeChatAtom, chatB.id);
    });
    expect(result.current.messages).toEqual([]);
    expect(store.get(runningChatIdsAtom)).toEqual(new Set([chatA.id]));
    expect(store.get(chatGenerationInProgressAtom)).toBe(true);
    expect(
      screen.getByRole("button", { name: chatA.title }),
    ).toHaveAccessibleDescription("Running");
    expect(getChatRuntime(store).deleteChats(chatA.id)).toBe(false);
    expect(getChatRuntime(store).deleteChats(null)).toBe(false);
    await act(async () => {
      finishResponse("Reply to A");
      await request;
    });
    const messagesA = store.get(chatStateAtom).chats.get(chatA.id)?.messages;
    expect(messagesA?.at(-1)?.parts).toContainEqual({
      type: "text",
      text: "Reply to A",
      state: "done",
    });
    expect(store.get(chatStateAtom).chats.get(chatB.id)?.messages).toEqual([]);
    expect(store.get(runningChatIdsAtom).size).toBe(0);
    expect(store.get(chatGenerationInProgressAtom)).toBe(false);
    expect(store.get(unreadChatIdsAtom)).toEqual(new Set([chatA.id]));
    expect(
      screen.getByRole("button", { name: chatA.title }),
    ).toHaveAccessibleDescription("Unread response");
    fireEvent.click(screen.getByRole("button", { name: chatA.title }));
    expect(
      screen.getByRole("button", { name: chatA.title }),
    ).not.toHaveAccessibleDescription("Unread response");
    expect(store.get(unreadChatIdsAtom).size).toBe(0);
    expect(getChatRuntime(store).sessions.get(chatA.id)).toBe(sessionA);
    expect(result.current.messages).toEqual(messagesA);
  });

  it("does not mark a response unread while its chat is visible", async () => {
    const finishResponse = mockChatResponse();
    const chatA = makeChat("Chat A");
    const { result, store } = setup([chatA]);
    expect(getChatRuntime(store).viewedChatId).toBe(chatA.id);
    let request: Promise<void>;
    act(() => {
      request = result.current.sendMessage({
        role: "user",
        parts: [{ type: "text", text: "Hello" }],
      });
    });
    await act(async () => {
      finishResponse("Visible reply");
      await request;
    });
    expect(store.get(unreadChatIdsAtom).size).toBe(0);
  });

  it.each([
    { type: "abort", reason: "user_cancelled" },
    { type: "error", errorText: "Generation failed" },
  ] satisfies UIMessageChunk[])(
    "does not mark an interrupted response unread ($type)",
    async (end) => {
      const finishResponse = mockChatResponse();
      const chatA = makeChat("Chat A");
      const chatB = makeChat("Chat B");
      const { result, store } = setup([chatA, chatB]);
      let request: Promise<void>;
      act(() => {
        request = result.current.sendMessage({
          role: "user",
          parts: [{ type: "text", text: "Hello" }],
        });
        store.set(activeChatAtom, chatB.id);
      });
      await act(async () => {
        finishResponse("Partial", end);
        await request;
      });
      expect(store.get(unreadChatIdsAtom).size).toBe(0);
    },
  );

  it("marks a response unread while the browser tab is hidden and clears it on return", async () => {
    const finishResponse = mockChatResponse();
    const chatA = makeChat("Chat A");
    const { result, store } = setup([chatA]);
    const visibility = vi.spyOn(document, "visibilityState", "get");
    let request: Promise<void>;
    act(() => {
      request = result.current.sendMessage({
        role: "user",
        parts: [{ type: "text", text: "Hello" }],
      });
    });
    visibility.mockReturnValue("hidden");
    fireEvent(document, new Event("visibilitychange"));
    expect(getChatRuntime(store).viewedChatId).toBeNull();
    expect(store.get(chatGenerationInProgressAtom)).toBe(true);
    await act(async () => {
      finishResponse("Background reply");
      await request;
    });
    expect(store.get(unreadChatIdsAtom)).toEqual(new Set([chatA.id]));
    visibility.mockReturnValue("visible");
    fireEvent(document, new Event("visibilitychange"));
    expect(getChatRuntime(store).viewedChatId).toBe(chatA.id);
    expect(store.get(unreadChatIdsAtom).size).toBe(0);
  });

  it("marks a response unread while the sidebar is hidden and clears it when reopened", async () => {
    const finishResponse = mockChatResponse();
    const chatA = makeChat("Chat A");
    const store = createStore();
    let visible = true;
    const wrapper = ({ children }: PropsWithChildren) => (
      <Provider store={store}>
        <LazyActivity mode={visible ? "visible" : "hidden"}>
          {children}
        </LazyActivity>
      </Provider>
    );
    const { result, rerender } = renderHook(
      () => useChatSession(useAtomValue(activeChatAtom)),
      { wrapper },
    );
    act(() =>
      store.set(chatStateAtom, {
        chats: new Map([[chatA.id, chatA]]),
        activeChatId: chatA.id,
        openChatIds: [chatA.id],
      }),
    );
    let request: Promise<void>;
    act(() => {
      request = result.current.sendMessage({
        role: "user",
        parts: [{ type: "text", text: "Hello" }],
      });
    });
    visible = false;
    rerender();
    expect(getChatRuntime(store).viewedChatId).toBeNull();
    await act(async () => {
      finishResponse("Sidebar was hidden");
      await request;
    });
    expect(store.get(unreadChatIdsAtom)).toEqual(new Set([chatA.id]));
    visible = true;
    rerender();
    expect(getChatRuntime(store).viewedChatId).toBe(chatA.id);
    expect(store.get(unreadChatIdsAtom).size).toBe(0);
    expect(result.current.messages.at(-1)?.parts).toContainEqual({
      type: "text",
      text: "Sidebar was hidden",
      state: "done",
    });
  });

  it("deletes idle sessions and their tabs without recreating history when storage is full", () => {
    const chatA = makeChat("Chat A");
    const chatB = makeChat("Chat B");
    const savedMessage: UIMessage = {
      id: "saved",
      role: "user",
      parts: [{ type: "text", text: "Hello" }],
    };
    chatA.messages = [savedMessage];
    chatB.messages = [savedMessage];
    const { store } = setup([chatA, chatB]);
    const sessions = getChatRuntime(store).sessions;
    expect(
      window.localStorage.getItem("marimo:ai:chatState:v5"),
    ).not.toBeNull();
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new DOMException("Storage is full", "QuotaExceededError");
      });
    try {
      act(() => {
        expect(getChatRuntime(store).deleteChats(null)).toBe(true);
      });
      expect(store.get(chatStateAtom)).toEqual({
        chats: new Map(),
        activeChatId: null,
        openChatIds: [],
      });
      expect(sessions.has(chatA.id)).toBe(false);
      expect(sessions.has(chatB.id)).toBe(false);
      expect(window.localStorage.getItem("marimo:ai:chatState:v5")).toBeNull();
      expect(setItem).not.toHaveBeenCalled();
    } finally {
      setItem.mockRestore();
    }
  });

  it("closes only that tab's session and reopens its partial messages from history", () => {
    const chatA = makeChat("Chat A");
    const chatB = makeChat("Chat B");
    const { result, store, wrapper } = setup([chatA, chatB]);
    const sessionA = getChatRuntime(store).sessions.get(chatA.id);
    const partialMessages: UIMessage[] = [
      {
        id: "reply",
        role: "assistant",
        parts: [{ type: "text", text: "Partial" }],
      },
    ];
    act(() => {
      if (!sessionA) {
        throw new Error("Expected a session for Chat A");
      }
      sessionA.controller.messages = partialMessages;
      store.set(activeChatAtom, chatB.id);
    });
    const sessionB = getChatRuntime(store).sessions.get(chatB.id);
    if (!sessionA || !sessionB) {
      throw new Error("Expected sessions for both chats");
    }
    const closeA = vi.spyOn(sessionA, "close");
    const closeB = vi.spyOn(sessionB, "close");
    render(<ChatTabs />, { wrapper });
    act(() => store.set(unreadChatIdsAtom, new Set([chatA.id])));
    fireEvent.click(screen.getByRole("button", { name: "Close Chat A" }));
    expect(closeA).toHaveBeenCalledOnce();
    expect(closeB).not.toHaveBeenCalled();
    expect(getChatRuntime(store).sessions.has(chatA.id)).toBe(false);
    expect(store.get(unreadChatIdsAtom).has(chatA.id)).toBe(false);
    expect(getChatRuntime(store).sessions.get(chatB.id)).toBe(sessionB);
    expect(store.get(chatStateAtom)).toMatchObject({
      activeChatId: chatB.id,
      openChatIds: [chatB.id],
    });
    expect(store.get(chatStateAtom).chats.get(chatA.id)?.messages).toEqual(
      partialMessages,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close Chat B" }));
    expect(closeB).toHaveBeenCalledOnce();
    expect(store.get(chatStateAtom).activeChatId).toBeNull();
    expect(result.current.id).not.toBe(chatA.id);
    expect(result.current.id).not.toBe(chatB.id);
    expect(result.current.messages).toEqual([]);

    act(() => {
      store.set(activeChatAtom, chatA.id);
    });
    expect(getChatRuntime(store).sessions.get(chatA.id)).not.toBe(sessionA);
    expect(result.current.messages).toEqual(partialMessages);
    expect(result.current.status).toBe("ready");
  });
});
