/* Copyright 2024 Marimo. All rights reserved. */

import type { Chat } from "@/core/ai/state";

const DATE_GROUP_CONFIG = [
  { label: "Today", days: 0 },
  { label: "Yesterday", days: 1 },
  { label: "2d ago", days: 2 },
  { label: "3d ago", days: 3 },
  { label: "This week", days: 7 },
  { label: "This month", days: 30 },
] as const;

interface DateGroup {
  label: string;
  days: number;
  chats: Chat[];
}

// Utility function to group chats by date periods
export const groupChatsByDate = (chats: Chat[]): DateGroup[] => {
  const now = Date.now();
  const oneDayMs = 24 * 60 * 60 * 1000;

  // Initialize groups with empty chat arrays
  const groups: DateGroup[] = DATE_GROUP_CONFIG.map((config) => ({
    ...config,
    chats: [],
  }));

  const olderGroup: DateGroup = {
    label: "Older",
    days: Infinity,
    chats: [],
  };

  // Helper function to determine which group a chat belongs to
  const getGroupForChat = (daysDiff: number): DateGroup => {
    // Use switch for exact day matches, then handle ranges
    switch (daysDiff) {
      case 0:
        return groups[0]; // Today
      case 1:
        return groups[1]; // Yesterday
      case 2:
        return groups[2]; // 2d ago
      case 3:
        return groups[3]; // 3d ago
      default:
        // Handle range-based grouping for older chats
        if (daysDiff >= 4 && daysDiff <= 7) {
          return groups[4]; // This week
        } else if (daysDiff >= 8 && daysDiff <= 30) {
          return groups[5]; // This month
        }
        // Everything else goes to Older
        return olderGroup;
    }
  };

  for (const chat of chats) {
    const daysDiff = Math.floor((now - chat.updatedAt) / oneDayMs);
    const targetGroup = getGroupForChat(daysDiff);
    targetGroup.chats.push(chat);
  }

  // Return only non-empty groups
  return [...groups, olderGroup].filter((group) => group.chats.length > 0);
};
