/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { Loader2Icon, XIcon } from "lucide-react";
import { memo, useId, useMemo } from "react";
import useEvent from "react-use-event-hook";
import { Button } from "@/components/ui/button";
import {
  chatSessionsAtom,
  runningChatIdsAtom,
  unreadChatIdsAtom,
} from "@/core/ai/chat-session";
import {
  activeChatAtom,
  closeChatTab,
  type Chat,
  type ChatId,
  chatStateAtom,
} from "@/core/ai/state";
import { cn } from "@/utils/cn";

interface ChatTabProps {
  chat: Chat;
  isActive: boolean;
  isRunning: boolean;
  hasUnreadResponse: boolean;
  onSelect: (chatId: ChatId) => void;
  onClose: (chatId: ChatId) => void;
}

const ChatTab = memo<ChatTabProps>(
  ({ chat, isActive, isRunning, hasUnreadResponse, onSelect, onClose }) => {
    const statusId = useId();
    let statusDescription: string | undefined;
    if (isRunning) {
      statusDescription = "Running";
    } else if (hasUnreadResponse) {
      statusDescription = "Unread response";
    }
    return (
      <div
        className={cn(
          "group flex items-center gap-1 px-2 py-1 text-sm border-r border-border cursor-pointer min-w-0 max-w-[160px] transition-colors",
          isActive
            ? "bg-background text-foreground relative z-1"
            : "bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground",
        )}
      >
        <button
          type="button"
          className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
          title={chat.title}
          aria-label={chat.title}
          aria-describedby={statusDescription ? statusId : undefined}
          aria-pressed={isActive}
          onClick={() => onSelect(chat.id)}
        >
          {isRunning && (
            <Loader2Icon
              aria-hidden="true"
              className="size-3 shrink-0 animate-spin motion-reduce:animate-none"
            />
          )}
          {!isRunning && hasUnreadResponse && (
            <span
              aria-hidden="true"
              className="size-1.5 shrink-0 rounded-full bg-primary"
            />
          )}
          <span className="truncate">{chat.title}</span>
          {statusDescription && (
            <span id={statusId} className="sr-only">
              {statusDescription}
            </span>
          )}
        </button>
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Close ${chat.title}`}
          className={cn(
            "h-4 w-4 p-0 shrink-0 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 hover:bg-destructive/20 hover:text-destructive",
            isActive && "opacity-100",
          )}
          onClick={(e) => {
            e.stopPropagation();
            onClose(chat.id);
          }}
        >
          <XIcon className="h-3 w-3" />
        </Button>
      </div>
    );
  },
);
ChatTab.displayName = "ChatTab";

export const ChatTabs = memo(() => {
  const [chatState, setChatState] = useAtom(chatStateAtom);
  const setActiveChat = useSetAtom(activeChatAtom);
  const sessions = useAtomValue(chatSessionsAtom);
  const runningChatIds = useAtomValue(runningChatIdsAtom);
  const unreadChatIds = useAtomValue(unreadChatIdsAtom);

  const openChats = useMemo(() => {
    return chatState.openChatIds
      .map((id) => chatState.chats.get(id))
      .filter((chat): chat is Chat => chat !== undefined);
  }, [chatState.chats, chatState.openChatIds]);

  const handleSelectChat = useEvent((chatId: ChatId) => {
    setActiveChat(chatId);
  });

  const handleCloseChat = useEvent((chatId: ChatId) => {
    const session = sessions.get(chatId);
    if (session) {
      void session.close();
      sessions.delete(chatId);
    }
    setChatState((prev) => closeChatTab(prev, chatId));
  });

  if (openChats.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center border-b bg-muted/20 overflow-hidden shrink-0">
      <div className="flex min-w-0 flex-1 overflow-x-auto">
        {openChats.map((chat) => (
          <ChatTab
            key={chat.id}
            chat={chat}
            isActive={chat.id === chatState.activeChatId}
            isRunning={runningChatIds.has(chat.id)}
            hasUnreadResponse={unreadChatIds.has(chat.id)}
            onSelect={handleSelectChat}
            onClose={handleCloseChat}
          />
        ))}
      </div>
    </div>
  );
});
ChatTabs.displayName = "ChatTabs";
