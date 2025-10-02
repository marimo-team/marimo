/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { BotMessageSquareIcon, ClockIcon, SearchIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { useLocale } from "react-aria";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip } from "@/components/ui/tooltip";
import { type ChatId, chatStateAtom } from "@/core/ai/state";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/dates";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { groupChatsByDate } from "./chat-history-utils";

interface ChatHistoryPopoverProps {
  activeChatId: ChatId | undefined;
  setActiveChat: (id: ChatId | null) => void;
}

export const ChatHistoryPopover: React.FC<ChatHistoryPopoverProps> = ({
  activeChatId,
  setActiveChat,
}) => {
  const chatState = useAtomValue(chatStateAtom);
  const { locale } = useLocale();
  const [searchQuery, setSearchQuery] = useState("");

  const chats = useMemo(() => {
    return [...chatState.chats.values()].sort(
      (a, b) => b.updatedAt - a.updatedAt,
    );
  }, [chatState.chats]);

  const filteredChats = useMemo(() => {
    if (!searchQuery.trim()) {
      return chats;
    }
    return chats.filter((chat) =>
      chat.title.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [chats, searchQuery]);

  const groupedChats = useMemo(() => {
    return groupChatsByDate(filteredChats);
  }, [filteredChats]);

  return (
    <Popover>
      <Tooltip content="Previous chats">
        <PopoverTrigger asChild={true}>
          <Button variant="text" size="icon">
            <ClockIcon className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent className="w-[480px] p-0" align="start" side="right">
        <div className="pt-3 px-3 w-full">
          <Input
            placeholder="Search chat history..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="text-xs"
          />
        </div>
        <ScrollArea className="h-[450px] p-2">
          <div className="space-y-3">
            {chats.length === 0 && (
              <PanelEmptyState
                title="No chats yet"
                description="Start a new chat to get started"
                icon={<BotMessageSquareIcon />}
              />
            )}
            {filteredChats.length === 0 && searchQuery && chats.length > 0 && (
              <PanelEmptyState
                title="No chats found"
                description={`No chats match "${searchQuery}"`}
                icon={<SearchIcon />}
              />
            )}
            {groupedChats.map((group, idx) => (
              <div key={group.label} className="space-y-2">
                <div className="text-xs px-1 text-muted-foreground/60">
                  {group.label}
                </div>
                <div>
                  {group.chats.map((chat) => (
                    <button
                      key={chat.id}
                      className={cn(
                        "w-full p-1 rounded-md cursor-pointer text-left flex items-center justify-between",
                        chat.id === activeChatId && "bg-accent",
                        chat.id !== activeChatId && "hover:bg-muted/20",
                      )}
                      onClick={() => {
                        setActiveChat(chat.id);
                      }}
                      type="button"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm truncate">{chat.title}</div>
                      </div>
                      <div className="text-xs text-muted-foreground/60 ml-2 flex-shrink-0">
                        {timeAgo(chat.updatedAt, locale)}
                      </div>
                    </button>
                  ))}
                </div>
                {/* If last group, don't show a divider */}
                {idx !== groupedChats.length - 1 && <hr />}
              </div>
            ))}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
};
