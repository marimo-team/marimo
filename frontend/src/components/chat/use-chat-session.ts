/* Copyright 2026 Marimo. All rights reserved. */

import { safeValidateUIMessages } from "ai";
import { useAtomValue, useStore } from "jotai";
import { useEffect } from "react";
import useEvent from "react-use-event-hook";
import { createChatSession } from "@/core/ai/chat-session";
import { getChatRuntime } from "@/core/ai/chat-runtime";
import { replaceMessagesInChat } from "@/core/ai/chat-utils";
import { useChatState } from "@/core/ai/use-chat-state";
import { useStagedAICellsActions } from "@/core/ai/staged-cells";
import { type Chat, chatOptionsAtom, chatStateAtom } from "@/core/ai/state";
import type { ToolNotebookContext } from "@/core/ai/tools/base";
import { FRONTEND_TOOL_REGISTRY } from "@/core/ai/tools/registry";
import { useCellActions } from "@/core/cells/actions";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { aiAtom } from "@/core/config/config";
import { useRequestClient } from "@/core/network/requests";
import { useRuntimeManager } from "@/core/runtime/config";
import { Logger } from "@/utils/Logger";
import { useEventListener } from "@/hooks/useEventListener";
import { StreamingChunkTransport } from "../editor/ai/transport/chat-transport";
import {
  describeChatAbortReason,
  getAbortReasonFromChunk,
  resolveChatAbortReason,
  USER_CANCELLED_ABORT_REASON,
} from "./chat-abort";
import {
  handleToolCall,
  hasPendingToolCalls,
  hasUnresolvedToolCalls,
  shouldFlushQueue,
} from "./chat-utils";
import { useChatControllerId } from "./use-chat-controller-id";

export function useChatSession(activeChat: Chat | null | undefined) {
  const store = useStore();
  const runtime = getChatRuntime(store);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool } = useRequestClient();
  const { addStagedCell } = useStagedAICellsActions();
  const { createCell } = useCellActions();
  const { chatControllerId: chatId, renewDraftChatId: renewDraftId } =
    useChatControllerId(activeChat?.id);
  const toolContext: ToolNotebookContext = {
    addStagedCell,
    createCell,
    store,
  };

  const session = runtime.getOrCreateSession(chatId, () => {
    let streamAbortReason: string | null = null;
    const nextSession = createChatSession({
      id: chatId,
      store,
      messages: activeChat?.messages ?? [],
      sendAutomaticallyWhen: ({ messages }) => hasPendingToolCalls(messages),
      shouldFlushQueue: ({ messages, isError, isAbort }) =>
        shouldFlushQueue({
          isError,
          isAbort,
          hasPendingToolCalls: hasPendingToolCalls(messages),
          hasUnresolvedToolCalls: hasUnresolvedToolCalls(messages),
        }),
      onRunningChange: (isRunning) => runtime.setRunning(chatId, isRunning),
      transport: new StreamingChunkTransport(
        {
          api: runtimeManager.getAiURL("chat").toString(),
          headers: () => runtimeManager.headers(),
          prepareSendMessagesRequest: async (options) => {
            // Surface schema drift even though the server sanitizes messages.
            const validation = await safeValidateUIMessages({
              messages: options.messages,
            });
            if (!validation.success) {
              Logger.debug(
                "Outgoing chat messages failed AI SDK schema validation",
                validation.error,
              );
            }

            const chatMode = store.get(aiAtom)?.mode || "ask";
            const tools = FRONTEND_TOOL_REGISTRY.getToolSchemas(chatMode);
            return {
              api: runtimeManager.getAiURL("chat").toString(),
              body: {
                tools,
                ...options,
                uiMessages: options.messages,
                includeOtherCode: getCodes(""),
                options: store.get(chatOptionsAtom),
              },
            };
          },
        },
        (chunk) => {
          if (chunk.type === "abort") {
            streamAbortReason =
              getAbortReasonFromChunk(chunk) ?? USER_CANCELLED_ABORT_REASON;
          }
        },
      ),
      saveMessages: (messages) => {
        store.set(chatStateAtom, (chatState) =>
          replaceMessagesInChat({ chatState, chatId, messages }),
        );
      },
      onFinish: ({ messages, isAbort, isError, finishReason }) => {
        const wasAborted = isAbort || streamAbortReason !== null;
        const reason = resolveChatAbortReason({
          isAbort: wasAborted,
          streamReason: streamAbortReason,
        });
        streamAbortReason = null;
        nextSession.setAbortNotice(
          reason === null ? null : describeChatAbortReason(reason),
        );
        if (reason !== null) {
          Logger.debug("Chat stream aborted", { reason, finishReason });
        }
        runtime.finishChat({ chatId, messages, isAbort: wasAborted, isError });
      },
      onToolCall: async ({ toolCall, addToolOutput }) => {
        await handleToolCall({
          invokeAiTool,
          addToolOutput,
          toolCall: {
            toolName: toolCall.toolName,
            toolCallId: toolCall.toolCallId,
            input: toolCall.input,
          },
          toolContext,
        });
      },
      onError: (error) => {
        Logger.error("An error occurred:", error);
      },
    });
    return nextSession;
  });

  useEffect(() => {
    runtime.pruneDrafts(chatId);
  }, [chatId, runtime]);
  const chat = useChatState(session.controller);
  const { queuedMessages, abortNotice, turn } = useAtomValue(session.stateAtom);

  const updateViewedChat = useEvent(() => {
    if (document.visibilityState === "visible") {
      runtime.viewChat(chatId);
    } else {
      runtime.hideChat(chatId);
    }
  });
  useEventListener(document, "visibilitychange", updateViewedChat);
  useEffect(() => {
    updateViewedChat();
    // Activity cleans up effects when the sidebar hides, while streams continue.
    return () => runtime.hideChat(chatId);
  }, [chatId, runtime, updateViewedChat]);

  return {
    ...chat,
    id: chatId,
    sendMessage: session.sendMessage,
    regenerate: session.regenerate,
    stop: session.stop,
    addToolApprovalResponse: session.addToolApprovalResponse,
    submitOrQueue: session.submitOrQueue,
    queuedMessages,
    abortNotice,
    isTurnActive: session.isActive(),
    turnStartedAt: turn?.startedAt ?? null,
    renewDraftChatId: renewDraftId,
  };
}
