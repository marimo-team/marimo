/* Copyright 2024 Marimo. All rights reserved. */

import type { Chat } from "@/core/ai/state";

// Group chats by time periods and pinned status
export function groupChats(chats: Chat[]) {
  const now = Date.now();
  const oneDay = 24 * 60 * 60 * 1000;
  const sevenDays = 7 * oneDay;
  const thirtyDays = 30 * oneDay;

  const groups = {
    pinned: [] as Chat[],
    today: [] as Chat[],
    last7Days: [] as Chat[],
    last30Days: [] as Chat[],
    older: [] as Chat[],
  };

  chats.forEach((chat) => {
    const timeDiff = now - chat.updatedAt;

    if (chat.pinned) {
      groups.pinned.push(chat);
    } else if (timeDiff < oneDay) {
      groups.today.push(chat);
    } else if (timeDiff < sevenDays) {
      groups.last7Days.push(chat);
    } else if (timeDiff < thirtyDays) {
      groups.last30Days.push(chat);
    } else {
      groups.older.push(chat);
    }
  });

  return groups;
}
