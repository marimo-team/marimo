/* Copyright 2024 Marimo. All rights reserved. */

import { useChat } from "@ai-sdk/react";
import { storePrompt } from "@marimo-team/codemirror-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type { Message } from "ai/react";
import { useAtom, useAtomValue } from "jotai";
import {
  BotMessageSquareIcon,
  ClockIcon,
  FileIcon,
  Loader2,
  PaperclipIcon,
  PlusIcon,
  SendIcon,
  SettingsIcon,
  SquareIcon,
  XIcon,
} from "lucide-react";
import {
  type Dispatch,
  memo,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
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
import { addMessageToChat } from "@/core/ai/chat-utils";
import { useModelChange } from "@/core/ai/config";
import {
  activeChatAtom,
  type Chat,
  type ChatId,
  type ChatState,
  chatStateAtom,
} from "@/core/ai/state";
import type { ChatAttachment } from "@/core/ai/types";
import { aiAtom, aiEnabledAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { FeatureFlagged } from "@/core/config/feature-flag";
import { useRequestClient } from "@/core/network/requests";
import { useRuntimeManager } from "@/core/runtime/config";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/dates";
import { blobToString } from "@/utils/fileToBase64";
import { Logger } from "@/utils/Logger";
import { generateUUID } from "@/utils/uuid";
import { AIModelDropdown } from "../ai/ai-model-dropdown";
import { useOpenSettingsToTab } from "../app-config/state";
import { PromptInput } from "../editor/ai/add-cell-with-ai";
import { getAICompletionBody } from "../editor/ai/completion-utils";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { Input } from "../ui/input";
import { Tooltip, TooltipProvider } from "../ui/tooltip";
import { MarkdownRenderer } from "./markdown-renderer";
import { ReasoningAccordion } from "./reasoning-accordion";
import { ToolCallAccordion } from "./tool-call-accordion";

interface ChatHeaderProps {
  onNewChat: () => void;
  activeChatId: ChatId | undefined;
  setActiveChat: (id: ChatId | null) => void;
  chats: Chat[];
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  onNewChat,
  activeChatId,
  setActiveChat,
  chats,
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
  message: Message;
  index: number;
  onEdit: (index: number, newValue: string) => void;
  setChatState: Dispatch<SetStateAction<ChatState>>;
  chatState: ChatState;
  isStreamingReasoning: boolean;
  isLast: boolean;
}

const ChatMessage: React.FC<ChatMessageProps> = memo(
  ({ message, index, onEdit, isStreamingReasoning, isLast }) => (
    <div
      className={cn(
        "flex group relative",
        message.role === "user" ? "justify-end" : "justify-start",
      )}
    >
      {message.role === "user" ? (
        <div className="w-[95%] bg-background border p-1 rounded-sm">
          <PromptInput
            key={message.id}
            value={message.content}
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
      ) : (
        <div className="w-[95%] break-words">
          <div className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyClipboardIcon className="h-3 w-3" value={message.content} />
          </div>
          {message.parts?.map((part, i) => {
            switch (part.type) {
              case "text":
                return <MarkdownRenderer key={i} content={part.text} />;

              case "reasoning":
                return (
                  <ReasoningAccordion
                    reasoning={part.reasoning}
                    key={i}
                    index={i}
                    isStreaming={
                      isLast &&
                      isStreamingReasoning &&
                      // If there are multiple reasoning parts, only show the last one
                      i === (message.parts?.length || 0) - 1
                    }
                  />
                );

              case "tool-invocation":
                return (
                  <ToolCallAccordion
                    key={i}
                    index={i}
                    toolName={part.toolInvocation.toolName}
                    result={
                      part.toolInvocation.state === "result"
                        ? part.toolInvocation.result
                        : null
                    }
                    state={part.toolInvocation.state}
                  />
                );

              /* handle other part types … */
              default:
                return null;
            }
          })}
        </div>
      )}
    </div>
  ),
);
ChatMessage.displayName = "ChatMessage";

interface ChatInputFooterProps {
  isEmpty: boolean;
  onSendClick: () => void;
  isLoading: boolean;
  onStop: () => void;
  handleFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
}

const DEFAULT_MODE = "manual";

const FileAttachmentPill = ({
  file,
  className,
  onRemove,
}: {
  file: File;
  className?: string;
  onRemove: () => void;
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={cn(
        "py-1 px-1.5 bg-muted rounded-md cursor-pointer flex flex-row gap-1 items-center text-xs",
        className,
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isHovered ? (
        <XIcon className="h-3 w-3 mt-0.5" onClick={onRemove} />
      ) : (
        // TODO: Add icons for different file types
        <FileIcon className="h-3 w-3 mt-0.5" />
      )}
      {file.name}
    </div>
  );
};

const ChatInputFooter: React.FC<ChatInputFooterProps> = memo(
  ({
    isEmpty,
    onSendClick,
    isLoading,
    onStop,
    fileInputRef,
    handleFileChange,
  }) => {
    const ai = useAtomValue(aiAtom);
    const currentMode = ai?.mode || DEFAULT_MODE;
    const currentModel = ai?.models?.chat_model || DEFAULT_AI_MODEL;
    const { saveModeChange, saveModelChange } = useModelChange();

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

    return (
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
            value={currentModel}
            placeholder="Model"
            onSelect={(model) => saveModelChange(model, "chat")}
            triggerClassName="h-6 text-xs shadow-none! ring-0! bg-muted hover:bg-muted/30 rounded-sm"
            iconSize="small"
            showAddCustomModelDocs={true}
            forRole="chat"
          />
        </div>
        <div className="flex flex-row">
          <Button
            variant="text"
            size="icon"
            className="cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
            title="Attach a file"
          >
            <PaperclipIcon className="h-3.5 w-3.5" />
          </Button>
          <Input
            ref={fileInputRef}
            type="file"
            multiple={true}
            hidden={true}
            onChange={handleFileChange}
            // TODO: Add support for other file types
            accept="image/*"
          />

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
        </div>
      </div>
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
  handleFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
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
    handleFileChange,
    onClose,
  }) => {
    const handleSendClick = useEvent(() => {
      if (input.trim()) {
        onSubmit(undefined, input);
      }
    });

    return (
      <div className="border-t relative shrink-0 min-h-[80px] flex flex-col">
        <div className={cn("px-2 py-3 flex-1", inputClassName)}>
          <PromptInput
            inputRef={inputRef}
            value={input}
            onChange={setInput}
            onSubmit={onSubmit}
            onClose={onClose}
            placeholder={placeholder || "Type your message..."}
          />
        </div>
        <ChatInputFooter
          isEmpty={!input.trim()}
          onSendClick={handleSendClick}
          isLoading={isLoading}
          onStop={onStop}
          fileInputRef={fileInputRef}
          handleFileChange={handleFileChange}
        />
      </div>
    );
  },
);

ChatInput.displayName = "ChatInput";

export const ChatPanel = () => {
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
  const [chatState, setChatState] = useAtom(chatStateAtom);
  const [activeChat, setActiveChat] = useAtom(activeChatAtom);
  const [newThreadInput, setNewThreadInput] = useState("");
  const [files, setFiles] = useState<File[]>();
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool } = useRequestClient();

  const {
    messages,
    input,
    setInput,
    setMessages,
    append,
    handleSubmit,
    error,
    status,
    reload,
    stop,
  } = useChat({
    id: activeChat?.id,
    maxSteps: 10,
    initialMessages: activeChat?.messages || [],
    keepLastMessageOnError: true,
    // Throttle the messages and data updates to 100ms
    // experimental_throttle: 100,
    api: runtimeManager.getAiURL("chat").toString(),
    headers: runtimeManager.headers(),
    experimental_prepareRequestBody: (options) => {
      const completionBody = getAICompletionBody({
        input: options.messages.map((m) => m.content).join("\n"),
      });

      // Backend accepts attachments, so we convert the key
      const newOptions = {
        ...options,
        messages: options.messages.map((m) => ({
          ...m,
          attachments: m.experimental_attachments,
          experimental_attachments: undefined,
        })),
      };

      return {
        ...newOptions,
        ...completionBody,
      };
    },
    onFinish: (message) => {
      setChatState((prev) => {
        return addMessageToChat({
          chatState: prev,
          chatId: prev.activeChatId,
          messageId: message.id,
          role: "assistant",
          content: message.content,
          parts: message.parts,
          attachments: message.experimental_attachments,
        });
      });
    },
    onToolCall: async ({ toolCall }) => {
      try {
        const response = await invokeAiTool({
          toolName: toolCall.toolName,
          arguments: toolCall.args as Record<string, never>,
        });

        // This response triggers the onFinish callback
        return response.result || response.error;
      } catch (error) {
        Logger.error("Tool call failed:", error);
        return `Error: ${error instanceof Error ? error.message : String(error)}`;
      }
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
    onResponse: (response) => {
      Logger.debug("Received HTTP response from server:", response);
    },
  });

  const handleFileChange = useEvent(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (files) {
        setFiles([...files]);
      }
    },
  );

  const removeFile = useEvent((file: File) => {
    if (files) {
      setFiles(files.filter((f) => f !== file));
    }
  });

  const isLoading = status === "submitted" || status === "streaming";

  // Sync user messages from useChat to storage when they become available
  // Only when we are done loading, for performance.
  useEffect(() => {
    if (!chatState.activeChatId || messages.length === 0 || isLoading) {
      return;
    }

    // Only sync if the last message is from a user
    const lastMessage = messages[messages.length - 1];
    if (lastMessage?.role !== "user") {
      return;
    }

    const currentChat = chatState.chats.get(chatState.activeChatId);
    if (!currentChat) {
      return;
    }

    const storedMessageIds = new Set(currentChat.messages.map((m) => m.id));

    // Find user messages from useChat that aren't in storage yet
    const missingUserMessages = messages.filter(
      (m) => m.role === "user" && !storedMessageIds.has(m.id),
    );

    if (missingUserMessages.length > 0) {
      setChatState((prev) => {
        let result = prev;

        for (const userMessage of missingUserMessages) {
          result = addMessageToChat({
            chatState: result,
            chatId: prev.activeChatId,
            messageId: userMessage.id,
            role: "user",
            content: userMessage.content,
            parts: userMessage.parts,
            attachments: userMessage.experimental_attachments,
          });
        }

        return result;
      });
    }
  }, [
    messages,
    chatState.activeChatId,
    chatState.chats,
    setChatState,
    isLoading,
  ]);

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
  }, [chatState.activeChatId]);

  const createNewThread = async (
    initialMessage: string,
    initialAttachments?: File[],
  ) => {
    const CURRENT_TIME = Date.now();
    const newChat: Chat = {
      id: generateUUID() as ChatId,
      title:
        initialMessage.length > 50
          ? `${initialMessage.slice(0, 50)}...`
          : initialMessage,
      messages: [], // Don't pre-populate - let useChat handle it and sync back
      createdAt: CURRENT_TIME,
      updatedAt: CURRENT_TIME,
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

    const attachments =
      initialAttachments && initialAttachments.length > 0
        ? await convertToChatAttachments(initialAttachments)
        : undefined;

    // Trigger AI conversation with append
    append({
      id: generateUUID(),
      role: "user",
      content: initialMessage,
      experimental_attachments: attachments,
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
    // Truncate both useChat and storage
    setMessages((messages) => messages.slice(0, index));
    const activeChatId = chatState.activeChatId;
    if (activeChatId) {
      setChatState((prev) => {
        const nextChats = new Map(prev.chats);
        const activeChat = chatState.chats.get(activeChatId);
        if (activeChat) {
          nextChats.set(activeChat.id, {
            ...activeChat,
            messages: activeChat.messages.slice(0, index),
            updatedAt: Date.now(),
          });
        }

        return {
          ...prev,
          chats: nextChats,
        };
      });
    }

    append({
      role: "user",
      content: newValue,
    });
  });

  const handleChatInputSubmit = useEvent(
    (e: KeyboardEvent | undefined, newValue: string): void => {
      if (!newValue.trim()) {
        return;
      }
      if (newMessageInputRef.current?.view) {
        storePrompt(newMessageInputRef.current.view);
      }
      handleSubmit(e);
      setFiles(undefined);
    },
  );

  const handleReload = () => {
    reload();
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

  const sortedChats = useMemo(() => {
    return [...chatState.chats.values()].sort(
      (a, b) => b.updatedAt - a.updatedAt,
    );
  }, [chatState.chats]);

  const isNewThread = messages.length === 0;
  const chatInput = isNewThread ? (
    <ChatInput
      key="new-thread-input"
      placeholder="Ask anything, @ to include context about tables or dataframes"
      input={newThreadInput}
      inputRef={newThreadInputRef}
      inputClassName="px-1 py-0"
      setInput={setNewThreadInput}
      onSubmit={handleNewThreadSubmit}
      isLoading={isLoading}
      onStop={stop}
      fileInputRef={fileInputRef}
      handleFileChange={handleFileChange}
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
      handleFileChange={handleFileChange}
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
          chats={sortedChats}
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
          <ChatMessage
            key={message.id}
            message={message}
            index={idx}
            onEdit={handleMessageEdit}
            setChatState={setChatState}
            chatState={chatState}
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

function isLastMessageReasoning(messages: Message[]): boolean {
  if (messages.length === 0) {
    return false;
  }

  const lastMessage = messages.at(-1);
  if (!lastMessage) {
    return false;
  }

  if (lastMessage.role !== "assistant" || !lastMessage.parts) {
    return false;
  }

  const parts = lastMessage.parts;
  if (parts.length === 0) {
    return false;
  }

  // Check if the last part is reasoning
  const lastPart = parts[parts.length - 1];
  return lastPart.type === "reasoning";
}

async function convertToChatAttachments(
  files: File[],
): Promise<ChatAttachment[]> {
  const attachments = await Promise.all(
    files.map(async (file) => {
      return {
        name: file.name,
        url: await blobToString(file, "dataUrl"),
        contentType: file.type,
      };
    }),
  );

  return attachments;
}
