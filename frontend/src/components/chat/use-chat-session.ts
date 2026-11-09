/* Copyright 2026 Marimo. All rights reserved. */

import { safeValidateUIMessages } from "ai";
import { useAtomValue, useStore } from "jotai";
import { useEffect } from "react";
import useEvent from "react-use-event-hook";
import {
  type ChatSession,
  chatSessionsAtom,
  createChatSession,
  runningChatIdsAtom,
  unreadChatIdsAtom,
  viewedChatIdAtom,
  markChatReadAtom,
} from "@/core/ai/chat-session";
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
  const sessions = useAtomValue(chatSessionsAtom);
  const store = useStore();
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

  let session = sessions.get(chatId);
  if (!session) {
    let streamAbortReason: string | null = null;
    const nextSession: ChatSession = createChatSession({
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
      onRunningChange: (isRunning) => {
        if (isRunning) {
          store.set(markChatReadAtom, chatId);
        }
        store.set(runningChatIdsAtom, (prev) => {
          if (prev.has(chatId) === isRunning) {
            return prev;
          }
          const next = new Set(prev);
          if (isRunning) {
            next.add(chatId);
          } else {
            next.delete(chatId);
          }
          return next;
        });
      },
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
        store.set(
          nextSession.abortNoticeAtom,
          reason === null ? null : describeChatAbortReason(reason),
        );
        if (reason !== null) {
          Logger.debug("Chat stream aborted", { reason, finishReason });
        }
        if (
          !wasAborted &&
          !isError &&
          !hasPendingToolCalls(messages) &&
          !hasUnresolvedToolCalls(messages) &&
          store.get(nextSession.queuedMessagesAtom).length === 0 &&
          store.get(viewedChatIdAtom) !== chatId &&
          store.get(chatStateAtom).chats.has(chatId)
        ) {
          store.set(unreadChatIdsAtom, (prev) =>
            prev.has(chatId) ? prev : new Set(prev).add(chatId),
          );
        }
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
    session = nextSession;
    sessions.set(chatId, session);
  }

  const renewDraftChatId = useEvent(() => {
    if (!store.get(chatStateAtom).chats.has(chatId)) {
      sessions.delete(chatId);
    }
    renewDraftId();
  });
  const chat = useChatState(session.controller);
  const queuedMessages = useAtomValue(session.queuedMessagesAtom);
  const abortNotice = useAtomValue(session.abortNoticeAtom);
  const turnStartedAt = useAtomValue(session.turnStartedAtAtom);

  const updateViewedChat = useEvent(() => {
    if (document.visibilityState === "visible") {
      store.set(viewedChatIdAtom, chatId);
      store.set(markChatReadAtom, chatId);
    } else if (store.get(viewedChatIdAtom) === chatId) {
      store.set(viewedChatIdAtom, null);
    }
  });
  useEventListener(document, "visibilitychange", updateViewedChat);
  useEffect(() => {
    updateViewedChat();
    // Activity cleans up effects when the sidebar hides, while streams continue.
    return () => {
      if (store.get(viewedChatIdAtom) === chatId) {
        store.set(viewedChatIdAtom, null);
      }
    };
  }, [chatId, store, updateViewedChat]);

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
    turnStartedAt,
    renewDraftChatId,
  };
}
