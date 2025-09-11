/* Copyright 2024 Marimo. All rights reserved. */

import type { UIMessage } from "@ai-sdk/react";
import { useChat } from "@ai-sdk/react";
import { storePrompt } from "@marimo-team/codemirror-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { DefaultChatTransport, type ToolUIPart } from "ai";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import {
  AtSignIcon,
  BotMessageSquareIcon,
  ClockIcon,
  Loader2,
  PaperclipIcon,
  PlusIcon,
  SendIcon,
  SettingsIcon,
  SquareIcon,
} from "lucide-react";
import { memo, useEffect, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
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
import { AiModelId, type ProviderId } from "@/core/ai/ids/ids";
import {
  activeChatAtom,
  type Chat,
  type ChatId,
  chatStateAtom,
} from "@/core/ai/state";
import { aiAtom, aiEnabledAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { FeatureFlagged } from "@/core/config/feature-flag";
import { useRequestClient } from "@/core/network/requests";
import { useRuntimeManager } from "@/core/runtime/config";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/dates";
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
import { Input } from "../ui/input";
import { Tooltip, TooltipProvider } from "../ui/tooltip";
import { toast } from "../ui/use-toast";
import { AttachmentRenderer, FileAttachmentPill } from "./chat-components";
import {
  buildCompletionRequestBody,
  convertToFileUIPart,
  generateChatTitle,
  handleToolCall,
  hasPendingToolCalls,
  isLastMessageReasoning,
} from "./chat-utils";
import { MarkdownRenderer } from "./markdown-renderer";
import { ReasoningAccordion } from "./reasoning-accordion";
import { ToolCallAccordion } from "./tool-call-accordion";

// Default mode for the AI
const DEFAULT_MODE = "manual";

// We need to modify the backend to support attachments for other providers
// And other types
const PROVIDERS_THAT_SUPPORT_ATTACHMENTS = new Set<ProviderId>([
  "openai",
  "google",
  "anthropic",
]);
const SUPPORTED_ATTACHMENT_TYPES = ["image/*", "text/*"];
const MAX_ATTACHMENT_SIZE = 1024 * 1024 * 50; // 50MB

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
  const chatState = useAtomValue(chatStateAtom);
  const chats = useMemo(() => {
    return [...chatState.chats.values()].sort(
      (a, b) => b.updatedAt - a.updatedAt,
    );
  }, [chatState.chats]);

  return (
    <div className="flex border-b px-2 py-1 justify-between shrink-0 items-center">
      <Tooltip content="New chat">
        <Button variant="text" size="icon" onClick={onNewChat}>
          <PlusIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <div className="flex items-center gap-2">
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
        <Popover>
          <Tooltip content="Previous chats">
            <PopoverTrigger asChild={true}>
              <Button variant="text" size="icon">
                <ClockIcon className="h-4 w-4" />
              </Button>
            </PopoverTrigger>
          </Tooltip>
          <PopoverContent className="w-[520px] p-0" align="start" side="right">
            <ScrollArea className="h-[500px] p-4">
              <div className="space-y-4">
                {chats.length === 0 && (
                  <PanelEmptyState
                    title="No chats yet"
                    description="Start a new chat to get started"
                    icon={<BotMessageSquareIcon />}
                  />
                )}
                {chats.map((chat) => (
                  <button
                    key={chat.id}
                    className={cn(
                      "w-full p-3 rounded-md cursor-pointer hover:bg-accent text-left",
                      chat.id === activeChatId && "bg-accent",
                    )}
                    onClick={() => {
                      setActiveChat(chat.id);
                    }}
                    type="button"
                  >
                    <div className="font-medium">{chat.title}</div>
                    <div className="text-sm text-muted-foreground">
                      {timeAgo(chat.updatedAt)}
                    </div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </PopoverContent>
        </Popover>
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

function isToolPart(part: UIMessage["parts"][number]): part is ToolUIPart {
  return part.type.startsWith("tool-");
}

const ChatMessageDisplay: React.FC<ChatMessageProps> = memo(
  ({ message, index, onEdit, isStreamingReasoning, isLast }) => {
    const renderUserMessage = (message: UIMessage) => {
      const textParts = message.parts?.filter((p) => p.type === "text");
      const content = textParts?.map((p) => p.text).join("\n");
      const fileParts = message.parts?.filter((p) => p.type === "file");

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
      const textParts = message.parts.filter((p) => p.type === "text");
      const content = textParts.map((p) => p.text).join("\n");

      return (
        <div className="w-[95%] break-words">
          <div className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyClipboardIcon className="h-3 w-3" value={content || ""} />
          </div>
          {message.parts.map((part, i) => {
            if (isToolPart(part)) {
              return (
                <ToolCallAccordion
                  key={i}
                  index={i}
                  toolName={part.type}
                  result={part.output}
                  state={part.state}
                />
              );
            }

            switch (part.type) {
              case "text":
                return <MarkdownRenderer key={i} content={part.text} />;

              case "reasoning":
                return (
                  <ReasoningAccordion
                    reasoning={part.text}
                    key={i}
                    index={i}
                    isStreaming={
                      isLast &&
                      isStreamingReasoning &&
                      // If there are multiple reasoning parts, only show the last one
                      i === (message.parts.length || 0) - 1
                    }
                  />
                );

              case "dynamic-tool":
                return (
                  <ToolCallAccordion
                    key={i}
                    index={i}
                    toolName={part.type}
                    result={part.output}
                    state={part.state}
                  />
                );

              // These are cryptographic signatures, so we don't need to render them
              case "data-reasoning-signature":
                return null;

              /* handle other part types … */
              default:
                if (part.type.startsWith("data-")) {
                  Logger.log("Found data part", part);
                  return null;
                }

                Logger.error("Unhandled part type:", part.type);
                try {
                  return (
                    <MarkdownRenderer
                      key={i}
                      content={JSON.stringify(part, null, 2)}
                    />
                  );
                } catch (error) {
                  Logger.error("Error rendering part:", part.type, error);
                  return null;
                }
            }
          })}
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

    const modeOptions = [
      {
        value: "ask",
        label: "Ask",
        subtitle:
          "Use AI with access to read-only tools like documentation search",
      },
      {
        value: "manual",
        label: "Manual",
        subtitle: "Pure chat, no tool usage",
      },
    ];

    const isAttachmentSupported =
      PROVIDERS_THAT_SUPPORT_ATTACHMENTS.has(currentProvider);

    return (
      <TooltipProvider>
        <div className="px-3 py-2 border-t border-border/20 flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <FeatureFlagged feature="mcp_docs">
              <Select value={currentMode} onValueChange={saveModeChange}>
                <SelectTrigger className="h-6 text-xs border-border shadow-none! ring-0! bg-muted hover:bg-muted/30 py-0 px-2 gap-1 capitalize">
                  {currentMode}
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectLabel>AI Mode</SelectLabel>
                    {modeOptions.map((option) => (
                      <SelectItem
                        key={option.value}
                        value={option.value}
                        className="text-xs"
                      >
                        <div className="flex flex-col">
                          {option.label}
                          <div className="text-muted-foreground text-xs pt-1 block">
                            {option.subtitle}
                          </div>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </FeatureFlagged>
            <AIModelDropdown
              placeholder="Model"
              triggerClassName="h-6 text-xs shadow-none! ring-0! bg-muted hover:bg-muted/30 rounded-sm"
              iconSize="small"
              showAddCustomModelDocs={true}
              forRole="chat"
            />
          </div>
          <div className="flex flex-row">
            <Tooltip content="Add context">
              <Button variant="text" size="icon" onClick={onAddContext}>
                <AtSignIcon className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
            {isAttachmentSupported && (
              <>
                <Tooltip content="Attach a file">
                  <Button
                    variant="text"
                    size="icon"
                    className="cursor-pointer"
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach a file"
                  >
                    <PaperclipIcon className="h-3.5 w-3.5" />
                  </Button>
                </Tooltip>
                <Input
                  ref={fileInputRef}
                  type="file"
                  multiple={true}
                  hidden={true}
                  onChange={(event) => {
                    if (event.target.files) {
                      onAddFiles([...event.target.files]);
                    }
                  }}
                  accept={SUPPORTED_ATTACHMENT_TYPES.join(",")}
                />
              </>
            )}

            <Tooltip content="Submit">
              <Button
                variant="text"
                size="sm"
                className="h-6 w-6 p-0 hover:bg-muted/30 cursor-pointer"
                onClick={isLoading ? onStop : onSendClick}
                disabled={isLoading ? false : isEmpty}
              >
                {isLoading ? (
                  <SquareIcon className="h-3 w-3 fill-current" />
                ) : (
                  <SendIcon className="h-3 w-3" />
                )}
              </Button>
            </Tooltip>
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
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const { handleClick } = useOpenSettingsToTab();

  if (!aiEnabled) {
    return (
      <PanelEmptyState
        title="Chat with AI"
        description="AI is currently disabled. Add your API key to enable."
        action={
          <Button variant="outline" size="sm" onClick={() => handleClick("ai")}>
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
  const [files, setFiles] = useState<File[]>();
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool } = useRequestClient();

  const activeChatId = activeChat?.id;

  const {
    messages,
    sendMessage,
    error,
    status,
    regenerate,
    stop,
    addToolResult,
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

        return {
          body: {
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
      await handleToolCall({
        invokeAiTool,
        addToolResult,
        toolCall: {
          toolName: toolCall.toolName,
          toolCallId: toolCall.toolCallId,
          input: toolCall.input as Record<string, never>,
        },
      });
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
  });

  const onAddFiles = useEvent((files: File[]) => {
    if (files.length === 0) {
      return;
    }

    let fileSize = 0;
    for (const file of files) {
      fileSize += file.size;
    }

    if (fileSize > MAX_ATTACHMENT_SIZE) {
      toast({
        title: "File size exceeds 50MB limit",
        description: "Please remove some files and try again.",
      });
      return;
    }

    setFiles((prev) => [...(prev ?? []), ...files]);
  });

  const removeFile = useEvent((file: File) => {
    if (files) {
      setFiles(files.filter((f) => f !== file));
    }
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
    setFiles(undefined);
    setInput("");
  };

  const handleNewChat = useEvent(() => {
    setActiveChat(null);
    setInput("");
    setNewThreadInput("");
    setFiles(undefined);
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
      setFiles(undefined);
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
      onAddFiles={onAddFiles}
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
      onAddFiles={onAddFiles}
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
            <ErrorBanner error={error} />
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
