/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import { storePrompt } from "@marimo-team/codemirror-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type {
  ChatAddToolApproveResponseFunction,
  FileUIPart,
  TextUIPart,
} from "ai";
import { useAtom, useAtomValue, useSetAtom, useStore } from "jotai";
import {
  BotMessageSquareIcon,
  Loader2,
  PlusIcon,
  SettingsIcon,
} from "lucide-react";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { Button } from "@/components/ui/button";
import { getChatRuntime } from "@/core/ai/chat-runtime";
import type { QueuedChatMessage } from "@/core/ai/chat-session";
import { useAIConfigActions } from "@/core/ai/config";
import { AiModelId } from "@/core/ai/ids/ids";
import {
  activeChatAtom,
  addChatAndOpenTab,
  type Chat,
  type ChatId,
  chatStateAtom,
  pendingAiPromptAtom,
} from "@/core/ai/state";
import { aiAtom, aiModelConfiguredAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { isWasm } from "@/core/wasm/utils";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { AIModelDropdown } from "../ai/ai-model-dropdown";
import { useOpenSettingsToTab } from "../app-config/state";
import {
  PairWithAgentBanner,
  usePairWithAgentModal,
} from "../editor/actions/pair-with-agent";
import { PromptInput } from "../editor/ai/prompt-input";
import { PendingAICells } from "../editor/chrome/wrapper/pending-ai-cells";
import {
  addContextCompletion,
  isContextAttachment,
  resolveChatContext,
} from "../editor/ai/completion-utils";
import { PanelHeaderActions } from "../editor/chrome/panels/panel-header";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CopyClipboardIcon } from "../icons/copy-icon";
import "./chat-typography.css";
import { MCPStatusIndicator } from "../mcp/mcp-status-indicator";
import { Tooltip, TooltipProvider } from "../ui/tooltip";
import {
  AddContextButton,
  AttachFileButton,
  AttachmentRenderer,
  FileAttachmentPill,
  SendButton,
} from "./chat-components";
import { AgentActivity } from "./agent-activity";
import { getAnswerText, renderUIMessage } from "./chat-display";
import { UserMessage } from "./user-message";
import { ChatHistoryPopover } from "./chat-history-popover";
import { CapabilitiesPopover } from "./capabilities-popover";
import { NotebookAccessSelector } from "./notebook-access-selector";
import { ChatTabs } from "./chat-tabs";
import {
  convertToFileUIPart,
  generateChatTitle,
  PROVIDERS_THAT_SUPPORT_ATTACHMENTS,
  useFileState,
} from "./chat-utils";
import { focusInputAndMoveToEnd } from "@/core/codemirror/utils";
import ScrollToBottomButton from "./acp/scroll-to-bottom-button";
import { useChatSession } from "./use-chat-session";

const DEFAULT_MODE = "ask";

const QueuedMessageDisplay = memo(
  ({ message }: { message: QueuedChatMessage }) => {
    const textParts = message.parts.filter(
      (p): p is TextUIPart => p.type === "text",
    );
    const content = textParts.map((p) => p.text).join("\n");
    const fileParts = message.parts.filter(
      (p): p is FileUIPart => p.type === "file",
    );

    return (
      <div className="flex justify-end">
        <div className="w-[95%] bg-background border border-dashed p-2 rounded-[10px] opacity-70">
          {fileParts.map((filePart, idx) => (
            <AttachmentRenderer attachment={filePart} key={idx} />
          ))}
          <div className="flex items-center justify-end gap-2 text-sm text-muted-foreground">
            <span className="wrap-break-word">{content}</span>
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
          </div>
        </div>
      </div>
    );
  },
);
QueuedMessageDisplay.displayName = "QueuedMessageDisplay";

interface ChatHeaderProps {
  onNewChat: () => void;
  activeChatId: ChatId | undefined;
  setActiveChat: (chatId: ChatId | null) => void;
  onDeleteChats: (id: ChatId | null) => void;
  isLoading: boolean;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  onNewChat,
  activeChatId,
  setActiveChat,
  onDeleteChats,
  isLoading,
}) => {
  const { handleClick } = useOpenSettingsToTab();

  return (
    <PanelHeaderActions>
      <div className="mo-ai-panel flex w-full shrink-0 items-center font-sans text-sm">
        <div className="flex w-full items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="chat-control gap-1.5 font-normal"
            onClick={onNewChat}
          >
            <PlusIcon className="size-4" aria-hidden={true} />
            New chat
          </Button>
          <ChatHistoryPopover
            activeChatId={activeChatId}
            setActiveChat={setActiveChat}
            onDeleteChats={onDeleteChats}
            isLoading={isLoading}
          />
          <div className="ml-auto flex items-center gap-2">
            <MCPStatusIndicator />
            <Tooltip content="AI Settings">
              <Button
                className="chat-control"
                aria-label="AI Settings"
                variant="ghost"
                size="icon"
                onClick={() => handleClick("ai")}
              >
                <SettingsIcon className="size-4" aria-hidden={true} />
              </Button>
            </Tooltip>
          </div>
        </div>
      </div>
    </PanelHeaderActions>
  );
};

interface ChatMessageProps {
  message: UIMessage;
  index: number;
  onEdit: (index: number, newValue: string) => void;
  isLast: boolean;
  isActive: boolean;
  turnStartedAt: number | null;
  addToolApprovalResponse?: ChatAddToolApproveResponseFunction;
}

const ChatMessageDisplay: React.FC<ChatMessageProps> = memo(
  ({
    message,
    index,
    onEdit,
    isLast,
    isActive,
    turnStartedAt,
    addToolApprovalResponse,
  }) => {
    if (message.role === "user") {
      return (
        <div className="group flex justify-end">
          <UserMessage
            message={message}
            canEdit={!isActive}
            onEdit={(newValue) => onEdit(index, newValue)}
          />
        </div>
      );
    }

    return (
      <div className="group relative flex justify-start">
        <div className="w-[95%] wrap-break-word">
          <div className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
            <CopyClipboardIcon
              className="h-3 w-3"
              value={() => getAnswerText(message)}
            />
          </div>
          {renderUIMessage({
            message,
            isLast,
            isActive,
            turnStartedAt,
            addToolApprovalResponse,
          })}
        </div>
      </div>
    );
  },
);
ChatMessageDisplay.displayName = "ChatMessage";

interface ChatInputFooterProps {
  isEmpty: boolean;
  onSendClick: () => void;
  isLoading: boolean;
  onStop: () => void;
  onAddFiles: (files: File[]) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onAddContext: () => void;
}

const ChatInputFooter: React.FC<ChatInputFooterProps> = memo(
  ({
    isEmpty,
    onSendClick,
    isLoading,
    onStop,
    fileInputRef,
    onAddFiles,
    onAddContext,
  }) => {
    const ai = useAtomValue(aiAtom);
    const currentMode = ai?.mode || DEFAULT_MODE;
    const currentModel = ai?.models?.chat_model || DEFAULT_AI_MODEL;
    const currentProvider = AiModelId.parse(currentModel).providerId;

    const { saveModeChange } = useAIConfigActions();

    const isAttachmentSupported =
      PROVIDERS_THAT_SUPPORT_ATTACHMENTS.has(currentProvider);

    return (
      <TooltipProvider>
        <div className="chat-input-footer px-3 py-2 border-t border-border/20 flex items-center gap-2">
          <div className="chat-input-selectors flex min-w-0 flex-1 items-center gap-1">
            <NotebookAccessSelector
              value={currentMode}
              onValueChange={saveModeChange}
            />
            <AIModelDropdown
              placeholder="Model"
              triggerClassName="chat-control chat-selector h-6 text-xs rounded-sm min-w-0 max-w-[200px] flex-1"
              iconSize="small"
              showAddCustomModelDocs={true}
              forRole="chat"
            />
          </div>
          <div className="chat-input-actions flex shrink-0 items-center gap-0.5 ml-auto">
            <CapabilitiesPopover />
            <AddContextButton
              handleAddContext={onAddContext}
              isLoading={isLoading}
            />
            {isAttachmentSupported && (
              <AttachFileButton
                fileInputRef={fileInputRef}
                isLoading={isLoading}
                onAddFiles={onAddFiles}
              />
            )}
            <SendButton
              isLoading={isLoading}
              onStop={onStop}
              onSendClick={onSendClick}
              isEmpty={isEmpty}
            />
          </div>
        </div>
      </TooltipProvider>
    );
  },
);

ChatInputFooter.displayName = "ChatInputFooter";

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  onSubmit: (e: KeyboardEvent | undefined, value: string) => void;
  inputRef: React.RefObject<ReactCodeMirrorRef | null>;
  isLoading: boolean;
  onStop: () => void;
  onClose: () => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onAddFiles: (files: File[]) => void;
}

const ChatInput: React.FC<ChatInputProps> = memo(
  ({
    input,
    setInput,
    onSubmit,
    inputRef,
    isLoading,
    onStop,
    fileInputRef,
    onAddFiles,
    onClose,
  }) => {
    const openPairWithAgentModal = usePairWithAgentModal();
    const placeholderAction = useMemo(
      () =>
        isWasm()
          ? undefined
          : {
              beforeText: "Type your message or ",
              linkText: "pair your own coding agent",
              afterText: ". Use @ to reference variables and cells.",
              onClick: openPairWithAgentModal,
            },
      [openPairWithAgentModal],
    );

    const handleSendClick = useEvent(() => {
      if (input.trim()) {
        onSubmit(undefined, input);
      }
    });

    return (
      <div className="relative shrink-0 flex flex-col">
        <div className="px-2 py-1.5">
          <PromptInput
            className="max-h-[400px]"
            inputRef={inputRef}
            value={input}
            onChange={setInput}
            onSubmit={onSubmit}
            onClose={onClose}
            onAddFiles={onAddFiles}
            placeholder="Type your message. Use @ to reference variables and cells."
            placeholderAction={placeholderAction}
          />
        </div>
        <ChatInputFooter
          isEmpty={!input.trim()}
          onAddContext={() => addContextCompletion(inputRef)}
          onSendClick={handleSendClick}
          isLoading={isLoading}
          onStop={onStop}
          fileInputRef={fileInputRef}
          onAddFiles={onAddFiles}
        />
      </div>
    );
  },
);

ChatInput.displayName = "ChatInput";

const ChatPanel = () => {
  const aiConfigured = useAtomValue(aiModelConfiguredAtom);
  const { handleClick } = useOpenSettingsToTab();

  if (!aiConfigured) {
    return (
      <PanelEmptyState
        title="Chat with AI"
        description="No AI provider configured or Chat model not selected"
        action={
          <div className="flex flex-col gap-3">
            <Button
              variant="outline"
              size="sm"
              className="self-start"
              onClick={() => handleClick("ai", "ai-providers")}
            >
              Edit AI settings
            </Button>
            <PairWithAgentBanner />
          </div>
        }
        icon={<BotMessageSquareIcon />}
      />
    );
  }

  return <ChatPanelBody />;
};

const ChatPanelBody = () => {
  const setChatState = useSetAtom(chatStateAtom);
  const [activeChat, setActiveChat] = useAtom(activeChatAtom);
  const [pendingPrompt, setPendingPrompt] = useAtom(pendingAiPromptAtom);
  const [input, setInput] = useState("");
  const [newThreadInput, setNewThreadInput] = useState("");
  const [isScrolledToBottom, setIsScrolledToBottom] = useState(true);
  const { files, addFiles, clearFiles, removeFile } = useFileState();
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const store = useStore();
  const activeChatId = activeChat?.id;
  const {
    messages,
    sendMessage,
    error,
    regenerate,
    stop,
    addToolApprovalResponse,
    id: chatId,
    renewDraftChatId,
    queuedMessages,
    submitOrQueue,
    abortNotice,
    isTurnActive,
    turnStartedAt,
  } = useChatSession(activeChat);

  const handleScroll = useEvent(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    const { scrollTop, scrollHeight, clientHeight } = container;
    const hasOverflow = scrollHeight > clientHeight;
    const isAtBottom = hasOverflow
      ? Math.abs(scrollHeight - clientHeight - scrollTop) < 5
      : true;
    setIsScrolledToBottom(isAtBottom);
  });

  const scrollToBottom = useEvent((smooth = false) => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }

    container.scrollTo({
      top: container.scrollHeight,
      behavior: smooth ? "smooth" : "auto",
    });
  });

  useEffect(() => {
    setIsScrolledToBottom(true);
  }, [activeChatId]);

  useEffect(() => {
    if (!isScrolledToBottom) {
      return;
    }
    const frame = requestAnimationFrame(() => {
      scrollToBottom();
    });
    return () => cancelAnimationFrame(frame);
  }, [
    messages,
    queuedMessages,
    isTurnActive,
    isScrolledToBottom,
    scrollToBottom,
  ]);

  const startNewChatState = useEvent((initialMessage: string) => {
    const now = Date.now();
    const newChat: Chat = {
      id: chatId,
      title: generateChatTitle(initialMessage),
      messages: [],
      createdAt: now,
      updatedAt: now,
    };

    setChatState((prev) => addChatAndOpenTab(prev, newChat));
    renewDraftChatId();
  });

  const createNewThread = useEvent(
    async (initialMessage: string, initialAttachments?: File[]) => {
      startNewChatState(initialMessage);

      const fileParts =
        initialAttachments && initialAttachments.length > 0
          ? await convertToFileUIPart(initialAttachments)
          : undefined;
      const { contextPart, attachments } =
        await resolveChatContext(initialMessage);

      sendMessage({
        role: "user",
        parts: [
          { type: "text" as const, text: initialMessage },
          ...(contextPart ? [contextPart] : []),
          ...(fileParts ?? []),
          ...attachments,
        ],
      });
      clearFiles();
      setInput("");
    },
  );

  const handleNewChat = useEvent(() => {
    renewDraftChatId();
    setActiveChat(null);
    setInput("");
    setNewThreadInput("");
    clearFiles();
  });

  const handleDeleteChats = useEvent((id: ChatId | null) => {
    if (
      getChatRuntime(store).deleteChats(id) &&
      (id === null || id === activeChatId)
    ) {
      renewDraftChatId();
      setInput("");
      setNewThreadInput("");
      clearFiles();
    }
  });

  const handleMessageEdit = useEvent(
    async (index: number, newValue: string) => {
      const editedMessage = messages[index];
      // Re-resolve @-context while preserving user uploads.
      const userFileParts =
        editedMessage.parts?.filter(
          (p) => p.type === "file" && !isContextAttachment(p),
        ) ?? [];
      const { contextPart, attachments } = await resolveChatContext(newValue);

      const messageId = editedMessage.id;
      sendMessage({
        messageId,
        role: "user",
        parts: [
          { type: "text", text: newValue },
          ...(contextPart ? [contextPart] : []),
          ...userFileParts,
          ...attachments,
        ],
      });
    },
  );

  const handleChatInputSubmit = useEvent(
    async (e: KeyboardEvent | undefined, newValue: string): Promise<void> => {
      if (!newValue.trim()) {
        return;
      }
      if (newMessageInputRef.current?.view) {
        storePrompt(newMessageInputRef.current.view);
      }
      const fileParts = files ? await convertToFileUIPart(files) : undefined;
      const { contextPart, attachments } = await resolveChatContext(newValue);

      e?.preventDefault();
      submitOrQueue([
        { type: "text", text: newValue },
        ...(contextPart ? [contextPart] : []),
        ...(fileParts ?? []),
        ...attachments,
      ]);
      setInput("");
      clearFiles();
    },
  );

  const handleReload = () => {
    regenerate();
  };

  const handleNewThreadSubmit = useEvent(() => {
    if (!newThreadInput.trim()) {
      return;
    }
    if (newThreadInputRef.current?.view) {
      storePrompt(newThreadInputRef.current.view);
    }
    createNewThread(newThreadInput.trim(), files);
  });

  const handleOnCloseThread = () => newThreadInputRef.current?.editor?.blur();

  const submitPendingPrompt = useEvent(async (prompt: string) => {
    if (activeChatId == null) {
      startNewChatState(prompt);
      // Starting a chat swaps the new-thread input for the regular input;
      // carry over any draft the user had typed so it isn't lost.
      setInput(newThreadInput);
    }
    const { contextPart, attachments } = await resolveChatContext(prompt);
    submitOrQueue([
      { type: "text", text: prompt },
      ...(contextPart ? [contextPart] : []),
      ...attachments,
    ]);
  });

  const isNewThread = messages.length === 0;

  useEffect(() => {
    if (!pendingPrompt) {
      return;
    }
    setPendingPrompt(null);
    const { prompt, submit, append } = pendingPrompt;
    const applyPrompt = (draft: string) =>
      append
        ? draft.includes(prompt.trim())
          ? draft
          : `${draft}${draft ? " " : ""}${prompt}`
        : prompt;
    if (submit) {
      void submitPendingPrompt(prompt);
    } else if (isNewThread) {
      setNewThreadInput(applyPrompt);
      focusInputAndMoveToEnd(newThreadInputRef);
    } else {
      setInput(applyPrompt);
      focusInputAndMoveToEnd(newMessageInputRef);
    }
  }, [pendingPrompt, setPendingPrompt, isNewThread, submitPendingPrompt]);

  const chatInput = isNewThread ? (
    <ChatInput
      key="new-thread-input"
      input={newThreadInput}
      inputRef={newThreadInputRef}
      setInput={setNewThreadInput}
      onSubmit={handleNewThreadSubmit}
      isLoading={isTurnActive}
      onStop={stop}
      fileInputRef={fileInputRef}
      onAddFiles={addFiles}
      onClose={handleOnCloseThread}
    />
  ) : (
    <ChatInput
      input={input}
      setInput={setInput}
      onSubmit={handleChatInputSubmit}
      inputRef={newMessageInputRef}
      isLoading={isTurnActive}
      onStop={stop}
      onClose={() => newMessageInputRef.current?.editor?.blur()}
      fileInputRef={fileInputRef}
      onAddFiles={addFiles}
    />
  );

  const filesPills = files && files.length > 0 && (
    <div className="flex flex-row gap-1 flex-wrap px-3 pt-2">
      {files?.map((file) => (
        <FileAttachmentPill
          file={file}
          key={file.name}
          onRemove={() => removeFile(file)}
        />
      ))}
    </div>
  );

  const composer = (
    <div className="@container rounded-[10px] border border-border bg-background">
      {filesPills}
      {chatInput}
    </div>
  );

  return (
    <div className="mo-ai-panel flex flex-col flex-1 min-h-0 font-prose text-sm leading-6">
      <TooltipProvider>
        <ChatHeader
          onNewChat={handleNewChat}
          activeChatId={activeChat?.id}
          setActiveChat={setActiveChat}
          onDeleteChats={handleDeleteChats}
          isLoading={isTurnActive}
        />
        <ChatTabs />
      </TooltipProvider>

      <div className="flex-1 flex flex-col overflow-hidden relative min-h-0">
        <div
          className="flex-1 px-3 bg-background gap-4 py-3 flex flex-col overflow-y-auto"
          ref={scrollContainerRef}
          onScroll={handleScroll}
        >
          <TooltipProvider>
            {messages.map((message, idx) => {
              const isLast = idx === messages.length - 1;
              return (
                <ChatMessageDisplay
                  key={message.id}
                  message={message}
                  index={idx}
                  onEdit={handleMessageEdit}
                  isLast={isLast}
                  isActive={isTurnActive}
                  turnStartedAt={isLast ? turnStartedAt : null}
                  addToolApprovalResponse={addToolApprovalResponse}
                />
              );
            })}
          </TooltipProvider>

          {isTurnActive && messages.at(-1)?.role === "user" && (
            <AgentActivity
              running={true}
              thinking={true}
              timing={
                turnStartedAt == null ? undefined : { startedAt: turnStartedAt }
              }
            />
          )}

          {queuedMessages.map((message) => (
            <QueuedMessageDisplay key={message.id} message={message} />
          ))}

          {error && (
            <div className="flex items-center justify-center space-x-2 mb-4">
              <ErrorBanner error={error || new Error("Unknown error")} />
              <Button variant="outline" size="sm" onClick={handleReload}>
                Retry
              </Button>
            </div>
          )}

          {abortNotice && !isTurnActive && !error && (
            <div className="flex justify-center py-2">
              <span className="text-xs text-muted-foreground">
                {abortNotice}
              </span>
            </div>
          )}
        </div>

        <ScrollToBottomButton
          isVisible={
            !isScrolledToBottom &&
            (messages.length > 0 || queuedMessages.length > 0)
          }
          onScrollToBottom={() => scrollToBottom(true)}
        />
      </div>

      {!isTurnActive && <PendingAICells />}
      <div className="shrink-0 p-3">{composer}</div>
    </div>
  );
};

export default ChatPanel;
