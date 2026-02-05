/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import { useChat } from "@ai-sdk/react";
import { storePrompt } from "@marimo-team/codemirror-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { DefaultChatTransport, type FileUIPart, type TextUIPart } from "ai";
import { useAtom, useAtomValue, useSetAtom, useStore } from "jotai";
import {
  BotMessageSquareIcon,
  HatGlasses,
  Loader2,
  type LucideIcon,
  MessageCircleIcon,
  NotebookText,
  PaperclipIcon,
  PlusIcon,
  SettingsIcon,
} from "lucide-react";
import { memo, useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
} from "@/components/ui/select";
import { replaceMessagesInChat } from "@/core/ai/chat-utils";
import { useModelChange } from "@/core/ai/config";
import { AiModelId } from "@/core/ai/ids/ids";
import { useStagedAICellsActions } from "@/core/ai/staged-cells";
import {
  activeChatAtom,
  type Chat,
  type ChatId,
  chatStateAtom,
} from "@/core/ai/state";
import type { ToolNotebookContext } from "@/core/ai/tools/base";
import {
  type CopilotMode,
  FRONTEND_TOOL_REGISTRY,
} from "@/core/ai/tools/registry";
import { useCellActions } from "@/core/cells/cells";
import { aiAtom, aiEnabledAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { useRequestClient } from "@/core/network/requests";
import { useRuntimeManager } from "@/core/runtime/config";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { AIModelDropdown } from "../ai/ai-model-dropdown";
import { useOpenSettingsToTab } from "../app-config/state";
import { PromptInput } from "../editor/ai/add-cell-with-ai";
import {
  addContextCompletion,
  CONTEXT_TRIGGER,
} from "../editor/ai/completion-utils";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { MCPStatusIndicator } from "../mcp/mcp-status-indicator";
import { Tooltip, TooltipProvider } from "../ui/tooltip";
import {
  AddContextButton,
  AttachFileButton,
  AttachmentRenderer,
  FileAttachmentPill,
  SendButton,
} from "./chat-components";
import { renderUIMessage } from "./chat-display";
import { ChatHistoryPopover } from "./chat-history-popover";
import {
  buildCompletionRequestBody,
  convertToFileUIPart,
  generateChatTitle,
  handleToolCall,
  hasPendingToolCalls,
  isLastMessageReasoning,
  PROVIDERS_THAT_SUPPORT_ATTACHMENTS,
  useFileState,
} from "./chat-utils";

// Default mode for the AI
const DEFAULT_MODE = "manual";

interface ChatHeaderProps {
  onNewChat: () => void;
  activeChatId: ChatId | undefined;
  setActiveChat: (id: ChatId | null) => void;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  onNewChat,
  activeChatId,
  setActiveChat,
}) => {
  const { handleClick } = useOpenSettingsToTab();

  return (
    <div className="flex border-b px-2 py-1 justify-between shrink-0 items-center">
      <Tooltip content="New chat">
        <Button variant="text" size="icon" onClick={onNewChat}>
          <PlusIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <div className="flex items-center gap-2">
        <MCPStatusIndicator />
        <Tooltip content="AI Settings">
          <Button
            variant="text"
            size="xs"
            className="hover:bg-foreground/10 py-2"
            onClick={() => handleClick("ai")}
          >
            <SettingsIcon className="h-4 w-4" />
          </Button>
        </Tooltip>
        <ChatHistoryPopover
          activeChatId={activeChatId}
          setActiveChat={setActiveChat}
        />
      </div>
    </div>
  );
};

interface ChatMessageProps {
  message: UIMessage;
  index: number;
  onEdit: (index: number, newValue: string) => void;
  isStreamingReasoning: boolean;
  isLast: boolean;
}

const ChatMessageDisplay: React.FC<ChatMessageProps> = memo(
  ({ message, index, onEdit, isStreamingReasoning, isLast }) => {
    const renderUserMessage = (message: UIMessage) => {
      const textParts = message.parts?.filter(
        (p): p is TextUIPart => p.type === "text",
      );
      const content = textParts?.map((p) => p.text).join("\n");
      const fileParts = message.parts?.filter(
        (p): p is FileUIPart => p.type === "file",
      );

      return (
        <div className="w-[95%] bg-background border p-1 rounded-sm">
          {fileParts?.map((filePart, idx) => (
            <AttachmentRenderer attachment={filePart} key={idx} />
          ))}
          <PromptInput
            key={message.id}
            value={content}
            placeholder="Type your message..."
            onChange={() => {
              // noop
            }}
            onSubmit={(_e, newValue) => {
              if (!newValue.trim()) {
                return;
              }
              onEdit(index, newValue);
            }}
            onClose={() => {
              // noop
            }}
          />
        </div>
      );
    };

    const renderOtherMessage = (message: UIMessage) => {
      const textParts = message.parts.filter(
        (p): p is TextUIPart => p.type === "text",
      );
      const content = textParts.map((p) => p.text).join("\n");

      return (
        <div className="w-[95%] wrap-break-word">
          <div className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyClipboardIcon className="h-3 w-3" value={content || ""} />
          </div>
          {renderUIMessage({ message, isStreamingReasoning, isLast })}
        </div>
      );
    };

    return (
      <div
        className={cn(
          "flex group relative",
          message.role === "user" ? "justify-end" : "justify-start",
        )}
      >
        {message.role === "user"
          ? renderUserMessage(message)
          : renderOtherMessage(message)}
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

    const { saveModeChange } = useModelChange();

    const modeOptions: {
      value: CopilotMode;
      label: string;
      subtitle: string;
      Icon: LucideIcon;
    }[] = [
      {
        value: "manual",
        label: "Manual",
        subtitle: "Pure chat, no tool usage",
        Icon: MessageCircleIcon,
      },
      {
        value: "ask",
        label: "Ask",
        subtitle:
          "Use AI with access to read-only tools like documentation search",
        Icon: NotebookText,
      },
      {
        value: "agent",
        label: "Agent (beta)",
        subtitle: "Use AI with access to read and write tools",
        Icon: HatGlasses,
      },
    ];

    const isAttachmentSupported =
      PROVIDERS_THAT_SUPPORT_ATTACHMENTS.has(currentProvider);

    const CurrentModeIcon = modeOptions.find(
      (o) => o.value === currentMode,
    )?.Icon;

    return (
      <TooltipProvider>
        <div className="px-3 py-2 border-t border-border/20 flex flex-row flex-wrap items-center justify-between gap-1">
          <div className="flex items-center gap-2">
            <Select value={currentMode} onValueChange={saveModeChange}>
              <SelectTrigger className="h-6 text-xs border-border shadow-none! ring-0! bg-muted hover:bg-muted/30 py-0 px-2 gap-1.5">
                {CurrentModeIcon && <CurrentModeIcon className="h-3 w-3" />}
                <span className="capitalize">{currentMode}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel className="text-xs uppercase tracking-wider text-muted-foreground/70 font-medium">
                    AI Mode
                  </SelectLabel>
                  {modeOptions.map((option) => (
                    <SelectItem
                      key={option.value}
                      value={option.value}
                      className="text-xs py-1"
                    >
                      <div className="flex items-start gap-2.5">
                        <span className="mt-1 text-muted-foreground">
                          <option.Icon className="h-3 w-3" />
                        </span>
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold">{option.label}</span>
                          <span className="text-muted-foreground">
                            {option.subtitle}
                          </span>
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <AIModelDropdown
              placeholder="Model"
              triggerClassName="h-6 text-xs shadow-none! ring-0! bg-muted hover:bg-muted/30 rounded-sm"
              iconSize="small"
              showAddCustomModelDocs={true}
              forRole="chat"
            />
          </div>
          <div className="flex flex-row">
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
  placeholder?: string;
  input: string;
  inputClassName?: string;
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
    placeholder,
    input,
    inputClassName,
    setInput,
    onSubmit,
    inputRef,
    isLoading,
    onStop,
    fileInputRef,
    onAddFiles,
    onClose,
  }) => {
    const handleSendClick = useEvent(() => {
      if (input.trim()) {
        onSubmit(undefined, input);
      }
    });

    return (
      <div className="relative shrink-0 min-h-[80px] flex flex-col border-t">
        <div className={cn("px-2 py-3 flex-1", inputClassName)}>
          <PromptInput
            inputRef={inputRef}
            value={input}
            onChange={setInput}
            onSubmit={onSubmit}
            onClose={onClose}
            onAddFiles={onAddFiles}
            placeholder={placeholder || "Type your message..."}
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
  const aiConfigured = useAtomValue(aiEnabledAtom);
  const { handleClick } = useOpenSettingsToTab();

  if (!aiConfigured) {
    return (
      <PanelEmptyState
        title="Chat with AI"
        description="No AI provider configured or Chat model not selected"
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleClick("ai", "ai-providers")}
          >
            Edit AI settings
          </Button>
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
  const [input, setInput] = useState("");
  const [newThreadInput, setNewThreadInput] = useState("");
  const { files, addFiles, clearFiles, removeFile } = useFileState();
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool, sendRun } = useRequestClient();

  const activeChatId = activeChat?.id;
  const store = useStore();

  const { addStagedCell } = useStagedAICellsActions();
  const { createNewCell, prepareForRun } = useCellActions();
  const toolContext: ToolNotebookContext = {
    addStagedCell,
    createNewCell,
    prepareForRun,
    sendRun,
    store,
  };

  const {
    messages,
    sendMessage,
    error,
    status,
    regenerate,
    stop,
    addToolOutput,
    id: chatId,
  } = useChat({
    id: activeChatId,
    sendAutomaticallyWhen: ({ messages }) => hasPendingToolCalls(messages),
    messages: activeChat?.messages || [], // initial messages
    transport: new DefaultChatTransport({
      api: runtimeManager.getAiURL("chat").toString(),
      headers: runtimeManager.headers(),
      prepareSendMessagesRequest: async (options) => {
        const completionBody = await buildCompletionRequestBody(
          options.messages,
        );

        // Call this here to ensure the value is not stale
        const chatMode = store.get(aiAtom)?.mode || DEFAULT_MODE;
        const tools = FRONTEND_TOOL_REGISTRY.getToolSchemas(chatMode);

        return {
          body: {
            tools,
            ...options,
            ...completionBody,
          },
        };
      },
    }),
    onFinish: ({ messages }) => {
      setChatState((prev) => {
        return replaceMessagesInChat({
          chatState: prev,
          chatId: prev.activeChatId,
          messages: messages,
        });
      });
    },
    onToolCall: async ({ toolCall }) => {
      // Dynamic tool calls will throw an error for toolName
      // https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage#client-side-page
      if (toolCall.dynamic) {
        Logger.debug("Skipping dynamic tool call", toolCall);
        return;
      }

      await handleToolCall({
        invokeAiTool,
        addToolOutput,
        toolCall: {
          toolName: toolCall.toolName,
          toolCallId: toolCall.toolCallId,
          input: toolCall.input as Record<string, never>,
        },
        toolContext,
      });
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
  });

  const isLoading = status === "submitted" || status === "streaming";

  // Check if we're currently streaming reasoning in the latest message
  const isStreamingReasoning =
    isLoading && messages.length > 0 && isLastMessageReasoning(messages);

  // Scroll to the latest chat message at the bottom
  useEffect(() => {
    const scrollToBottom = () => {
      if (scrollContainerRef.current) {
        const container = scrollContainerRef.current;
        container.scrollTop = container.scrollHeight;
      }
    };

    requestAnimationFrame(scrollToBottom);
  }, [activeChatId]);

  const createNewThread = async (
    initialMessage: string,
    initialAttachments?: File[],
  ) => {
    const now = Date.now();
    const newChat: Chat = {
      id: chatId as ChatId,
      title: generateChatTitle(initialMessage),
      messages: [],
      createdAt: now,
      updatedAt: now,
    };

    // Create new chat and set as active
    setChatState((prev) => {
      const newChats = new Map(prev.chats);
      newChats.set(newChat.id, newChat);
      const newState = {
        ...prev,
        chats: newChats,
        activeChatId: newChat.id,
      };
      return newState;
    });

    const fileParts =
      initialAttachments && initialAttachments.length > 0
        ? await convertToFileUIPart(initialAttachments)
        : undefined;

    // Trigger AI conversation with append
    sendMessage({
      role: "user",
      parts: [
        {
          type: "text" as const,
          text: initialMessage,
        },
        ...(fileParts ?? []),
      ],
    });
    clearFiles();
    setInput("");
  };

  const handleNewChat = useEvent(() => {
    setActiveChat(null);
    setInput("");
    setNewThreadInput("");
    clearFiles();
  });

  const handleMessageEdit = useEvent((index: number, newValue: string) => {
    const editedMessage = messages[index];
    const fileParts = editedMessage.parts?.filter((p) => p.type === "file");

    const messageId = editedMessage.id;
    sendMessage({
      messageId: messageId, // replace the message
      role: "user",
      parts: [{ type: "text", text: newValue }, ...fileParts],
    });
  });

  const handleChatInputSubmit = useEvent(
    async (e: KeyboardEvent | undefined, newValue: string): Promise<void> => {
      if (!newValue.trim()) {
        return;
      }
      if (newMessageInputRef.current?.view) {
        storePrompt(newMessageInputRef.current.view);
      }
      const fileParts = files ? await convertToFileUIPart(files) : undefined;

      e?.preventDefault();
      sendMessage({
        text: newValue,
        files: fileParts,
      });
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

  const isNewThread = messages.length === 0;
  const chatInput = isNewThread ? (
    <ChatInput
      key="new-thread-input"
      placeholder={`Ask anything, ${CONTEXT_TRIGGER} to include context about tables or dataframes`}
      input={newThreadInput}
      inputRef={newThreadInputRef}
      inputClassName="px-1 py-0"
      setInput={setNewThreadInput}
      onSubmit={handleNewThreadSubmit}
      isLoading={isLoading}
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
      isLoading={isLoading}
      onStop={stop}
      onClose={() => newMessageInputRef.current?.editor?.blur()}
      fileInputRef={fileInputRef}
      onAddFiles={addFiles}
    />
  );

  const filesPills = files && files.length > 0 && (
    <div
      className={cn(
        "flex flex-row gap-1 flex-wrap p-1",
        isNewThread && "py-2 px-1",
      )}
    >
      {files?.map((file) => (
        <FileAttachmentPill
          file={file}
          key={file.name}
          onRemove={() => removeFile(file)}
        />
      ))}
    </div>
  );

  return (
    <div className="flex flex-col h-[calc(100%-53px)]">
      <TooltipProvider>
        <ChatHeader
          onNewChat={handleNewChat}
          activeChatId={activeChat?.id}
          setActiveChat={setActiveChat}
        />
      </TooltipProvider>

      <div
        className="flex-1 px-3 bg-(--slate-1) gap-4 py-3 flex flex-col overflow-y-auto"
        ref={scrollContainerRef}
      >
        {isNewThread && (
          <div className="rounded-md border bg-background">
            {filesPills}
            {chatInput}
          </div>
        )}

        {messages.map((message, idx) => (
          <ChatMessageDisplay
            key={message.id}
            message={message}
            index={idx}
            onEdit={handleMessageEdit}
            isStreamingReasoning={isStreamingReasoning}
            isLast={idx === messages.length - 1}
          />
        ))}

        {isLoading && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center space-x-2 mb-4">
            <ErrorBanner error={error || new Error("Unknown error")} />
            <Button variant="outline" size="sm" onClick={handleReload}>
              Retry
            </Button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {isLoading && (
        <div className="w-full flex justify-center items-center z-20 border-t">
          <Button variant="linkDestructive" size="sm" onClick={stop}>
            Stop
          </Button>
        </div>
      )}

      {/* For existing threads, we place the chat input at the bottom */}
      {!isNewThread && (
        <>
          {filesPills}
          {chatInput}
        </>
      )}
    </div>
  );
};

export default ChatPanel;
