/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useSetAtom } from "jotai";
import { XIcon } from "lucide-react";
import { memo, useMemo } from "react";
import useEvent from "react-use-event-hook";
import { Button } from "@/components/ui/button";
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
  onSelect: (chatId: ChatId) => void;
  onClose: (chatId: ChatId) => void;
}

const ChatTab = memo<ChatTabProps>(({ chat, isActive, onSelect, onClose }) => {
  return (
    <div
      className={cn(
        "group flex items-center gap-1 px-2 py-1 text-sm border-r border-border cursor-pointer min-w-0 max-w-[160px] transition-colors",
        isActive
          ? "bg-background text-foreground relative z-1"
          : "bg-muted/30 text-muted-foreground hover:bg-muted/50 hover:text-foreground",
      )}
      onClick={() => onSelect(chat.id)}
    >
      <span className="truncate flex-1 min-w-0" title={chat.title}>
        {chat.title}
      </span>
      <Button
        variant="ghost"
        size="sm"
        className={cn(
          "h-4 w-4 p-0 shrink-0 opacity-0 group-hover:opacity-100 hover:bg-destructive/20 hover:text-destructive",
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
});
ChatTab.displayName = "ChatTab";

export const ChatTabs = memo(() => {
  const [chatState, setChatState] = useAtom(chatStateAtom);
  const setActiveChat = useSetAtom(activeChatAtom);

  const openChats = useMemo(() => {
    return chatState.openChatIds
      .map((id) => chatState.chats.get(id))
      .filter((chat): chat is Chat => chat !== undefined);
  }, [chatState.chats, chatState.openChatIds]);

  const handleSelectChat = useEvent((chatId: ChatId) => {
    setActiveChat(chatId);
  });

  const handleCloseChat = useEvent((chatId: ChatId) => {
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
            onSelect={handleSelectChat}
            onClose={handleCloseChat}
          />
        ))}
      </div>
    </div>
  );
});
ChatTabs.displayName = "ChatTabs";
