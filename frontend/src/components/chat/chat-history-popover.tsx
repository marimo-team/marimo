/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  BotMessageSquareIcon,
  ClockIcon,
  SearchIcon,
  Trash2Icon,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useLocale } from "react-aria";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
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

const CHAT_HISTORY_WARNING_THRESHOLD = 50;

interface ChatHistoryPopoverProps {
  activeChatId: ChatId | undefined;
  setActiveChat: (id: ChatId | null) => void;
  onDeleteChats: (id: ChatId | null) => void;
  isLoading: boolean;
}

export const ChatHistoryPopover: React.FC<ChatHistoryPopoverProps> = ({
  activeChatId,
  setActiveChat,
  onDeleteChats,
  isLoading,
}) => {
  const chatState = useAtomValue(chatStateAtom);
  const { locale } = useLocale();
  const [searchQuery, setSearchQuery] = useState("");
  const [open, setOpen] = useState(false);
  const { openConfirm, closeModal } = useImperativeModal();

  const confirmDeleteAllChats = () => {
    // Close the popover before opening a modal so focus moves to the dialog.
    setOpen(false);
    openConfirm({
      title: "Delete all chats?",
      description:
        "This will permanently delete all chat history for all notebooks on this site in this browser. This cannot be undone.",
      variant: "destructive",
      confirmAction: (
        <AlertDialogDestructiveAction
          onClick={() => {
            onDeleteChats(null);
            closeModal();
          }}
        >
          Delete all chats
        </AlertDialogDestructiveAction>
      ),
    });
  };

  const chats = useMemo(() => {
    return [...chatState.chats.values()].toSorted(
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
    <Popover open={open} onOpenChange={setOpen}>
      <Tooltip content="Previous chats">
        <PopoverTrigger asChild={true}>
          <Button variant="text" size="icon" aria-label="Previous chats">
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
                    <div
                      key={chat.id}
                      className={cn(
                        "w-full rounded-md flex items-center justify-between",
                        chat.id === activeChatId && "bg-accent",
                        chat.id !== activeChatId && "hover:bg-muted/20",
                      )}
                    >
                      <button
                        className="flex flex-1 min-w-0 items-center justify-between p-1 text-left cursor-pointer"
                        onClick={() => setActiveChat(chat.id)}
                        type="button"
                      >
                        <span className="text-sm truncate">{chat.title}</span>
                        <span className="text-xs text-muted-foreground/60 ml-2 shrink-0">
                          {timeAgo(chat.updatedAt, locale)}
                        </span>
                      </button>
                      <Tooltip
                        content={
                          isLoading && chat.id === activeChatId
                            ? "Stop the response before deleting this chat"
                            : "Delete chat"
                        }
                      >
                        <Button
                          variant="text"
                          size="icon"
                          className="text-muted-foreground/90 hover:text-destructive transition-colors ml-px"
                          aria-label={`Delete chat: ${chat.title}`}
                          disabled={isLoading && chat.id === activeChatId}
                          onClick={() => onDeleteChats(chat.id)}
                        >
                          <Trash2Icon className="h-3.5 w-3.5" />
                        </Button>
                      </Tooltip>
                    </div>
                  ))}
                </div>
                {/* If last group, don't show a divider */}
                {idx !== groupedChats.length - 1 && <hr />}
              </div>
            ))}
          </div>
        </ScrollArea>
        {chats.length > 0 && (
          <div className="border-t p-2 flex items-center justify-between gap-2">
            {chats.length > CHAT_HISTORY_WARNING_THRESHOLD ? (
              <p className="text-xs text-muted-foreground">
                You have over <b>{CHAT_HISTORY_WARNING_THRESHOLD}</b> chats.
                Delete old chats to free up browser storage.
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Chats are shared across notebooks.
              </p>
            )}
            <Button
              variant="linkDestructive"
              size="xs"
              disabled={isLoading}
              onClick={confirmDeleteAllChats}
            >
              Delete all chats
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};
