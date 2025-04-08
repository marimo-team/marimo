/* Copyright 2024 Marimo. All rights reserved. */
import { useAtom, useAtomValue } from "jotai";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  BotMessageSquareIcon,
  ClockIcon,
  Loader2,
  PlusIcon,
} from "lucide-react";
import {
  chatStateAtom,
  activeChatAtom,
  type Chat,
  type ChatState,
} from "@/core/ai/state";
import {
  useState,
  useRef,
  useEffect,
  type SetStateAction,
  type Dispatch,
  memo,
} from "react";
import { generateUUID } from "@/utils/uuid";
import { type Message, useChat } from "ai/react";
import { PromptInput } from "../editor/ai/add-cell-with-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { Tooltip, TooltipProvider } from "../ui/tooltip";
import { asURL } from "@/utils/url";
import { API } from "@/core/network/api";
import { cn } from "@/utils/cn";
import { MarkdownRenderer } from "./markdown-renderer";
import { Logger } from "@/utils/Logger";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { getAICompletionBody } from "../editor/ai/completion-utils";
import { addMessageToChat } from "@/core/ai/chat-utils";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import { aiAtom, aiEnabledAtom } from "@/core/config/config";
import { useOpenSettingsToTab } from "../app-config/state";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { timeAgo } from "@/utils/dates";

interface ChatHeaderProps {
  onNewChat: () => void;
  activeChatId: string | undefined;
  setActiveChat: (id: string | null) => void;
  chats: Chat[];
  setMessages: (messages: Message[]) => void;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  onNewChat,
  activeChatId,
  setActiveChat,
  chats,
  setMessages,
}) => {
  const ai = useAtomValue(aiAtom);
  const { handleClick } = useOpenSettingsToTab();
  const model = ai?.open_ai?.model || "gpt-4-turbo";

  return (
    <div className="flex border-b px-2 py-1 justify-between flex-shrink-0 items-center">
      <div className="flex items-center gap-2">
        <Tooltip content="New chat">
          <Button variant="text" size="icon" onClick={onNewChat}>
            <PlusIcon className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Button
          variant="text"
          size="xs"
          className="hover:bg-foreground/10 py-2"
          onClick={() => handleClick("ai")}
        >
          {model}
        </Button>
      </div>
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
                <div
                  key={chat.id}
                  className={cn(
                    "p-3 rounded-md cursor-pointer hover:bg-accent",
                    chat.id === activeChatId && "bg-accent",
                  )}
                  onClick={() => {
                    setActiveChat(chat.id);
                    setMessages(
                      chat.messages.map(({ role, content, timestamp }) => ({
                        role,
                        content,
                        id: timestamp.toString(),
                      })),
                    );
                  }}
                >
                  <div className="font-medium">{chat.title}</div>
                  <div className="text-sm text-muted-foreground">
                    {timeAgo(chat.updatedAt)}
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </PopoverContent>
      </Popover>
    </div>
  );
};

interface ChatMessageProps {
  message: Message;
  index: number;
  theme: ResolvedTheme;
  onEdit: (index: number, newValue: string) => void;
  setChatState: Dispatch<SetStateAction<ChatState>>;
  chatState: ChatState;
}

const ChatMessage: React.FC<ChatMessageProps> = memo(
  ({ message, index, theme, onEdit, setChatState, chatState }) => (
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
            theme={theme}
            placeholder="Type your message..."
            onChange={() => {
              // noop
            }}
            onSubmit={(e, newValue) => {
              if (!newValue.trim()) {
                return;
              }
              onEdit(index, newValue);
              if (chatState.activeChatId) {
                setChatState((prev: ChatState) =>
                  addMessageToChat(
                    prev,
                    chatState.activeChatId,
                    "user",
                    newValue,
                  ),
                );
              }
            }}
            onClose={() => {
              // noop
            }}
          />
        </div>
      ) : (
        <div className="w-[95%]">
          <div className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyClipboardIcon className="h-3 w-3" value={message.content} />
          </div>
          <MarkdownRenderer content={message.content} />
        </div>
      )}
    </div>
  ),
);
ChatMessage.displayName = "ChatMessage";

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  onSubmit: (e: KeyboardEvent | undefined, value: string) => void;
  theme: ResolvedTheme;
  inputRef: React.RefObject<ReactCodeMirrorRef>;
}

const ChatInput: React.FC<ChatInputProps> = memo(
  ({ input, setInput, onSubmit, theme, inputRef }) => (
    <div className="px-2 py-3 border-t relative flex-shrink-0 min-h-[80px]">
      <PromptInput
        value={input}
        onChange={setInput}
        onSubmit={onSubmit}
        onClose={() => inputRef.current?.editor?.blur()}
        theme={theme}
        placeholder="Type your message..."
      />
    </div>
  ),
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
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  const {
    messages,
    input,
    setInput,
    setMessages,
    append,
    handleSubmit,
    error,
    isLoading,
    reload,
  } = useChat({
    keepLastMessageOnError: true,
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    api: asURL("api/ai/chat").toString(),
    headers: API.headers(),
    experimental_prepareRequestBody: (options) => {
      return {
        ...options,
        ...getAICompletionBody({
          input: options.messages.map((m) => m.content).join("\n"),
        }),
        includeOtherCode: getCodes(""),
      };
    },
    streamProtocol: "text",
    onFinish: (message) => {
      if (!chatState.activeChatId) {
        Logger.warn("No active chat");
        return;
      }
      setChatState((prev) =>
        addMessageToChat(prev, prev.activeChatId, "assistant", message.content),
      );
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
    onResponse: (response) => {
      Logger.debug("Received HTTP response from server:", response);
    },
  });
  const lastMessageText = messages.at(-1)?.content;
  useEffect(() => {
    if (isLoading) {
      const BUFFER = 150;
      const container = messagesEndRef.current?.parentElement;
      if (!container) {
        return;
      }

      const isNearBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight <
        BUFFER;

      if (isNearBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages, isLoading, lastMessageText]);

  const createNewThread = (initialMessage: string) => {
    const newChat: Chat = {
      id: generateUUID(),
      title: `${initialMessage.slice(0, 30)}...`,
      messages: [
        {
          role: "user",
          content: initialMessage,
          timestamp: Date.now(),
        },
      ],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    setChatState((prev) => ({
      chats: [...prev.chats, newChat],
      activeChatId: newChat.id,
    }));

    setMessages([]);
    setInput("");
    append({
      role: "user",
      content: initialMessage,
    });
  };

  const handleNewChat = () => {
    setActiveChat(null);
    setMessages([]);
    setInput("");
    setNewThreadInput("");
  };

  const handleMessageEdit = (index: number, newValue: string) => {
    setMessages((messages) => messages.slice(0, index));
    append({
      role: "user",
      content: newValue,
    });
  };

  const handleChatInputSubmit = (
    e: KeyboardEvent | undefined,
    newValue: string,
  ): void => {
    if (!newValue.trim()) {
      return;
    }
    handleSubmit(e);
    if (chatState.activeChatId) {
      setChatState((prev) =>
        addMessageToChat(prev, chatState.activeChatId, "user", newValue),
      );
    }
  };

  const handleReload = () => {
    reload();
  };

  const handleNewThreadSubmit = () => {
    newThreadInput.trim() && createNewThread(newThreadInput.trim());
  };

  const handleOnCloseThread = () => newThreadInputRef.current?.editor?.blur();

  return (
    <div className="flex flex-col h-[calc(100%-53px)]">
      <TooltipProvider>
        <ChatHeader
          onNewChat={handleNewChat}
          activeChatId={activeChat?.id}
          setActiveChat={setActiveChat}
          chats={chatState.chats}
          setMessages={setMessages}
        />
      </TooltipProvider>

      <div className="flex-1 px-3 bg-[var(--slate-1)] gap-4 py-3 flex flex-col overflow-y-auto">
        {(!messages || messages.length === 0) && (
          <div className="flex rounded-md border px-1 bg-background">
            <PromptInput
              key="new-thread-input"
              value={newThreadInput}
              placeholder="Ask anything, @ to include context about tables or dataframes"
              theme={theme}
              onClose={handleOnCloseThread}
              onChange={setNewThreadInput}
              onSubmit={handleNewThreadSubmit}
            />
          </div>
        )}

        {messages.map((message, idx) => (
          <ChatMessage
            key={idx}
            message={message}
            index={idx}
            theme={theme}
            onEdit={handleMessageEdit}
            setChatState={setChatState}
            chatState={chatState}
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

      {messages && messages.length > 0 && (
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={handleChatInputSubmit}
          theme={theme}
          inputRef={newMessageInputRef}
        />
      )}
    </div>
  );
};
