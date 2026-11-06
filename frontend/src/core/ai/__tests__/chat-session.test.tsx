/* Copyright 2026 Marimo. All rights reserved. */

import { act, render, screen, waitFor } from "@testing-library/react";
import type { ChatTransport, UIMessage, UIMessageChunk } from "ai";
import { describe, expect, it, vi } from "vitest";
import {
  hasPendingToolCalls,
  hasUnresolvedToolCalls,
  shouldFlushQueue,
} from "@/components/chat/chat-utils";
import { LazyActivity } from "@/components/utils/lazy-mount";
import { type ChatSession, createChatSession } from "../chat-session";
import type { ChatId } from "../state";
import { useChatState } from "../use-chat-state";

const CHAT_A = "chat-a" as ChatId;
const CHAT_B = "chat-b" as ChatId;
const USER_MESSAGE = {
  role: "user",
  parts: [{ type: "text", text: "Hello" }],
} satisfies Omit<UIMessage, "id">;

function createTransport() {
  const streams = new Map<
    string,
    ReadableStreamDefaultController<UIMessageChunk>
  >();
  const signals = new Map<string, AbortSignal | undefined>();
  const sendMessages = vi.fn<ChatTransport<UIMessage>["sendMessages"]>(
    async ({ chatId, abortSignal }) => {
      signals.set(chatId, abortSignal);
      return new ReadableStream<UIMessageChunk>({
        start(controller) {
          streams.set(chatId, controller);
          abortSignal?.addEventListener("abort", () => {
            controller.error(new DOMException("Aborted", "AbortError"));
          });
          controller.enqueue({ type: "start", messageId: `reply-${chatId}` });
          controller.enqueue({ type: "start-step" });
        },
      });
    },
  );
  const transport: ChatTransport<UIMessage> = {
    sendMessages,
    reconnectToStream: async () => null,
  };
  const write = (chatId: ChatId, ...chunks: UIMessageChunk[]) => {
    const stream = streams.get(chatId);
    if (!stream) {
      throw new Error(`No stream for ${chatId}`);
    }
    for (const chunk of chunks) {
      stream.enqueue(chunk);
    }
  };
  const finish = (chatId: ChatId) => {
    write(chatId, { type: "finish-step" }, { type: "finish" });
    streams.get(chatId)?.close();
  };
  return { transport, signals, write, finish, sendMessages };
}

function SessionView({ session }: { session: ChatSession }) {
  const { messages, status } = useChatState(session.controller);
  return <output>{JSON.stringify({ messages, status })}</output>;
}

async function createApprovalSession({
  trailingText,
}: {
  trailingText: boolean;
}) {
  const { transport, write, finish, sendMessages } = createTransport();
  const session = createChatSession({
    id: CHAT_A,
    transport,
    saveMessages: vi.fn(),
    onToolCall: vi.fn().mockResolvedValue(undefined),
    sendAutomaticallyWhen: ({ messages }) => hasPendingToolCalls(messages),
    shouldFlushQueue: ({ messages, isError, isAbort }) =>
      shouldFlushQueue({
        isError,
        isAbort,
        hasPendingToolCalls: hasPendingToolCalls(messages),
        hasUnresolvedToolCalls: hasUnresolvedToolCalls(messages),
      }),
  });
  const followUp = [
    { type: "text", text: "Follow-up" },
  ] satisfies UIMessage["parts"];
  const request = session.sendMessage(USER_MESSAGE);
  session.submitOrQueue(followUp);
  write(
    CHAT_A,
    {
      type: "tool-input-available",
      toolCallId: "call-1",
      toolName: "lookup",
      input: {},
      providerExecuted: true,
    },
    {
      type: "tool-approval-request",
      toolCallId: "call-1",
      approvalId: "approval-1",
    },
  );
  if (trailingText) {
    write(
      CHAT_A,
      { type: "text-start", id: "text" },
      { type: "text-delta", id: "text", delta: "Please approve." },
      { type: "text-end", id: "text" },
    );
  }
  finish(CHAT_A);
  await request;
  return { session, write, finish, sendMessages, followUp };
}

describe("chat sessions", () => {
  it.each([true, false])(
    "releases queued input when approval with trailing text resolves (approved=%s)",
    async (approved) => {
      const { session, finish, sendMessages, followUp } =
        await createApprovalSession({ trailingText: true });
      expect(sendMessages).toHaveBeenCalledOnce();
      expect(session.store.get(session.queuedMessagesAtom)).toEqual([
        { id: expect.any(String), parts: followUp },
      ]);

      await session.addToolApprovalResponse({ id: "approval-1", approved });
      await waitFor(() => expect(sendMessages).toHaveBeenCalledTimes(2));
      expect(sendMessages.mock.lastCall?.[0].messages.at(-1)).toEqual({
        id: expect.any(String),
        role: "user",
        parts: followUp,
      });
      expect(session.store.get(session.queuedMessagesAtom)).toEqual([]);
      finish(CHAT_A);
      await waitFor(() => expect(session.controller.status).toBe("ready"));
    },
  );

  it.each([true, false])(
    "waits for the approval continuation before releasing queued input (approved=%s)",
    async (approved) => {
      const { session, write, finish, sendMessages, followUp } =
        await createApprovalSession({ trailingText: false });
      await session.addToolApprovalResponse({ id: "approval-1", approved });
      await waitFor(() => expect(sendMessages).toHaveBeenCalledTimes(2));
      expect(session.store.get(session.queuedMessagesAtom)).toEqual([
        { id: expect.any(String), parts: followUp },
      ]);
      expect(sendMessages.mock.calls[1][0].messages.at(-1)?.role).toBe(
        "assistant",
      );

      write(
        CHAT_A,
        { type: "text-start", id: "answer" },
        { type: "text-delta", id: "answer", delta: "Approval handled." },
        { type: "text-end", id: "answer" },
      );
      finish(CHAT_A);
      await waitFor(() => expect(sendMessages).toHaveBeenCalledTimes(3));
      expect(sendMessages.mock.lastCall?.[0].messages.at(-1)).toEqual({
        id: expect.any(String),
        role: "user",
        parts: followUp,
      });
      expect(session.store.get(session.queuedMessagesAtom)).toEqual([]);
      finish(CHAT_A);
      await waitFor(() => expect(session.controller.status).toBe("ready"));
    },
  );

  it("keeps concurrent streams and their saved messages separate when switching chats", async () => {
    const { transport, write, finish } = createTransport();
    const saveA = vi.fn();
    const saveB = vi.fn();
    const sessionA = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages: saveA,
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    const sessionB = createChatSession({
      id: CHAT_B,
      transport,
      saveMessages: saveB,
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    const view = render(<SessionView session={sessionA} />);
    let requestA: Promise<void>;
    act(() => {
      requestA = sessionA.sendMessage(USER_MESSAGE);
      write(
        CHAT_A,
        { type: "text-start", id: "text-a" },
        { type: "text-delta", id: "text-a", delta: "Reply A" },
      );
    });
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Reply A"),
    );

    view.rerender(<SessionView session={sessionB} />);
    let requestB: Promise<void>;
    act(() => {
      requestB = sessionB.sendMessage(USER_MESSAGE);
      write(
        CHAT_B,
        { type: "text-start", id: "text-b" },
        { type: "text-delta", id: "text-b", delta: "Reply B" },
      );
    });
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Reply B"),
    );
    await act(async () => {
      write(CHAT_A, { type: "text-end", id: "text-a" });
      finish(CHAT_A);
      await requestA;
    });
    expect(saveA).toHaveBeenLastCalledWith(sessionA.controller.messages);
    expect(saveB).not.toHaveBeenCalledWith(sessionA.controller.messages);
    expect(screen.getByRole("status")).toHaveTextContent("Reply B");

    view.rerender(<SessionView session={sessionA} />);
    expect(screen.getByRole("status")).toHaveTextContent("Reply A");
    expect(screen.getByRole("status")).toHaveTextContent('"status":"ready"');
    await act(async () => {
      write(CHAT_B, { type: "text-end", id: "text-b" });
      finish(CHAT_B);
      await requestB;
    });
    expect(saveB).toHaveBeenLastCalledWith(sessionB.controller.messages);
  });

  it("finishes and saves while the sidebar Activity is hidden", async () => {
    const { transport, write, finish, signals } = createTransport();
    const saveMessages = vi.fn();
    const session = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages,
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    const view = render(
      <LazyActivity mode="visible">
        <SessionView session={session} />
      </LazyActivity>,
    );
    let request: Promise<void>;
    act(() => {
      request = session.sendMessage(USER_MESSAGE);
    });
    view.rerender(
      <LazyActivity mode="hidden">
        <SessionView session={session} />
      </LazyActivity>,
    );
    await act(async () => {
      write(
        CHAT_A,
        { type: "text-start", id: "text" },
        { type: "text-delta", id: "text", delta: "Finished in background" },
        { type: "text-end", id: "text" },
      );
      finish(CHAT_A);
      await request;
    });
    expect(signals.get(CHAT_A)?.aborted).toBe(false);
    expect(saveMessages).toHaveBeenLastCalledWith(session.controller.messages);
    view.rerender(
      <LazyActivity mode="visible">
        <SessionView session={session} />
      </LazyActivity>,
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Finished in background",
      ),
    );
    expect(screen.getByRole("status")).toHaveTextContent('"status":"ready"');
  });

  it("aborts a closed chat, drops queued follow-ups, and saves its partial response without stopping another chat", async () => {
    const { transport, write, finish, signals, sendMessages } =
      createTransport();
    const saveMessages = vi.fn();
    const sessionA = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages,
      onToolCall: vi.fn().mockResolvedValue(undefined),
      shouldFlushQueue: () => true,
    });
    const sessionB = createChatSession({
      id: CHAT_B,
      transport,
      saveMessages: vi.fn(),
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    const requestA = sessionA.sendMessage(USER_MESSAGE);
    const requestB = sessionB.sendMessage(USER_MESSAGE);
    sessionA.submitOrQueue([{ type: "text", text: "Do not send after close" }]);
    write(
      CHAT_A,
      { type: "text-start", id: "text" },
      { type: "text-delta", id: "text", delta: "Partial response" },
    );
    await waitFor(() =>
      expect(sessionA.controller.messages.at(-1)?.parts).toContainEqual({
        type: "text",
        text: "Partial response",
        state: "streaming",
      }),
    );
    await sessionA.close();
    await requestA;
    expect(signals.get(CHAT_A)?.aborted).toBe(true);
    expect(signals.get(CHAT_B)?.aborted).toBe(false);
    expect(sessionA.store.get(sessionA.queuedMessagesAtom)).toEqual([]);
    expect(sendMessages).toHaveBeenCalledTimes(2);
    expect(saveMessages).toHaveBeenLastCalledWith(sessionA.controller.messages);
    expect(saveMessages.mock.lastCall?.[0].at(-1).parts).toContainEqual({
      type: "text",
      text: "Partial response",
      state: "streaming",
    });
    finish(CHAT_B);
    await requestB;
  });

  it("releases a queued follow-up while hidden without sending it to the selected chat", async () => {
    const { transport, write, finish, sendMessages } = createTransport();
    const sessionA = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages: vi.fn(),
      onToolCall: vi.fn().mockResolvedValue(undefined),
      shouldFlushQueue: () => true,
    });
    const sessionB = createChatSession({
      id: CHAT_B,
      transport,
      saveMessages: vi.fn(),
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    const view = render(
      <LazyActivity mode="visible">
        <SessionView session={sessionA} />
      </LazyActivity>,
    );
    act(() => {
      sessionA.submitOrQueue(USER_MESSAGE.parts);
      sessionA.submitOrQueue([{ type: "text", text: "Follow-up for A" }]);
    });
    expect(sessionA.store.get(sessionA.queuedMessagesAtom)).toEqual([
      {
        id: expect.any(String),
        parts: [{ type: "text", text: "Follow-up for A" }],
      },
    ]);
    view.rerender(
      <LazyActivity mode="hidden">
        <SessionView session={sessionA} />
      </LazyActivity>,
    );
    await act(async () => {
      write(
        CHAT_A,
        { type: "text-start", id: "first" },
        { type: "text-delta", id: "first", delta: "First reply" },
        { type: "text-end", id: "first" },
      );
      finish(CHAT_A);
    });
    await waitFor(() => expect(sendMessages).toHaveBeenCalledTimes(2));
    expect(sendMessages.mock.calls[1][0].chatId).toBe(CHAT_A);
    expect(sendMessages.mock.calls[1][0].messages.at(-1)?.parts).toEqual([
      { type: "text", text: "Follow-up for A" },
    ]);
    expect(sessionA.store.get(sessionA.queuedMessagesAtom)).toEqual([]);
    view.rerender(
      <LazyActivity mode="visible">
        <SessionView session={sessionB} />
      </LazyActivity>,
    );
    expect(sessionB.controller.messages).toEqual([]);
    await act(async () => {
      write(
        CHAT_A,
        { type: "text-start", id: "second" },
        { type: "text-delta", id: "second", delta: "Second reply" },
        { type: "text-end", id: "second" },
      );
      finish(CHAT_A);
    });
    await waitFor(() => expect(sessionA.controller.status).toBe("ready"));
    expect(sendMessages).toHaveBeenCalledTimes(2);
  });

  it("returns tool results to the background chat and continues its next turn", async () => {
    const { transport, write, finish, sendMessages } = createTransport();
    let finishTool: () => void = vi.fn();
    const toolResult = new Promise<void>((resolve) => {
      finishTool = resolve;
    });
    const onToolCall = vi.fn<
      Parameters<typeof createChatSession>[0]["onToolCall"]
    >(async ({ addToolOutput }) => {
      await toolResult;
      addToolOutput({
        tool: "lookup",
        toolCallId: "call-1",
        output: "Result for A",
      });
    });
    const sessionA = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages: vi.fn(),
      onToolCall,
      sendAutomaticallyWhen: ({ messages }) => {
        const lastPart = messages.at(-1)?.parts.at(-1);
        return (
          lastPart?.type === "tool-lookup" &&
          lastPart.state === "output-available"
        );
      },
    });
    const sessionB = createChatSession({
      id: CHAT_B,
      transport,
      saveMessages: vi.fn(),
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    const view = render(<SessionView session={sessionA} />);
    let request: Promise<void>;
    act(() => {
      request = sessionA.sendMessage(USER_MESSAGE);
      write(CHAT_A, {
        type: "tool-input-available",
        toolName: "lookup",
        toolCallId: "call-1",
        input: {},
      });
      finish(CHAT_A);
    });
    await waitFor(() => expect(onToolCall).toHaveBeenCalledOnce());
    view.rerender(<SessionView session={sessionB} />);
    await act(async () => {
      finishTool();
    });
    await waitFor(() => expect(sendMessages).toHaveBeenCalledTimes(2));
    await act(async () => {
      write(
        CHAT_A,
        { type: "text-start", id: "answer" },
        { type: "text-delta", id: "answer", delta: "Used the tool result" },
        { type: "text-end", id: "answer" },
      );
      finish(CHAT_A);
      await request;
    });
    expect(sessionA.controller.messages.at(-1)?.parts).toContainEqual({
      type: "tool-lookup",
      toolCallId: "call-1",
      state: "output-available",
      input: {},
      output: "Result for A",
    });
    expect(sessionB.controller.messages).toEqual([]);
    expect(sessionA.controller.status).toBe("ready");
    expect(sendMessages.mock.calls.map(([options]) => options.chatId)).toEqual([
      CHAT_A,
      CHAT_A,
    ]);
  });

  it("ignores late tool results after close and never starts another turn", async () => {
    const { transport, write, finish, sendMessages } = createTransport();
    let finishTool: () => void = vi.fn();
    const toolResult = new Promise<void>((resolve) => {
      finishTool = resolve;
    });
    const onToolCall = vi.fn(
      async ({
        addToolOutput,
      }: {
        addToolOutput: (output: {
          tool: string;
          toolCallId: string;
          output: string;
        }) => void;
      }) => {
        await toolResult;
        addToolOutput({
          tool: "lookup",
          toolCallId: "call-1",
          output: "Late result",
        });
      },
    );
    const session = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages: vi.fn(),
      onToolCall,
      sendAutomaticallyWhen: () => true,
    });
    const request = session.sendMessage(USER_MESSAGE);
    write(CHAT_A, {
      type: "tool-input-available",
      toolName: "lookup",
      toolCallId: "call-1",
      input: {},
    });
    finish(CHAT_A);
    await waitFor(() => expect(onToolCall).toHaveBeenCalledOnce());
    await session.close();
    finishTool();
    await request;
    expect(session.controller.messages.at(-1)?.parts).toContainEqual({
      type: "tool-lookup",
      toolCallId: "call-1",
      state: "input-available",
      input: {},
    });
    expect(sendMessages).toHaveBeenCalledOnce();
  });

  it("does not send after closing during asynchronous message preparation", async () => {
    const { transport, sendMessages } = createTransport();
    const session = createChatSession({
      id: CHAT_A,
      transport,
      saveMessages: vi.fn(),
      onToolCall: vi.fn().mockResolvedValue(undefined),
    });
    await session.close();
    await session.sendMessage(USER_MESSAGE);
    await session.regenerate();
    expect(sendMessages).not.toHaveBeenCalled();
  });
});
