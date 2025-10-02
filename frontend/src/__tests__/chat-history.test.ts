/* Copyright 2024 Marimo. All rights reserved. */

import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { groupChatsByDate } from "../components/chat/chat-history-utils";
import type { Chat } from "../core/ai/state";

// Mock current time for consistent testing
const mockNow = new Date("2024-01-15T12:00:00Z").getTime();

// Mock Date.now to return our fixed time
const originalDateNow = Date.now;
beforeAll(() => {
  Date.now = () => mockNow;
});

afterAll(() => {
  Date.now = originalDateNow;
});

describe("groupChatsByDate", () => {
  const createMockChat = (daysAgo: number, title: string): Chat => ({
    id: `chat-${daysAgo}` as Chat["id"],
    title,
    messages: [],
    createdAt: mockNow - daysAgo * 24 * 60 * 60 * 1000,
    updatedAt: mockNow - daysAgo * 24 * 60 * 60 * 1000,
  });

  it("should group chats correctly by date periods", () => {
    const chats: Chat[] = [
      createMockChat(0, "Today chat"),
      createMockChat(1, "Yesterday chat"),
      createMockChat(2, "2 days ago chat"),
      createMockChat(3, "3 days ago chat"),
      createMockChat(5, "5 days ago chat"), // Should go to "This week"
      createMockChat(10, "10 days ago chat"), // Should go to "This month"
      createMockChat(40, "40 days ago chat"), // Should go to "Older"
    ];

    const result = groupChatsByDate(chats);

    // Should have 7 groups
    expect(result).toHaveLength(chats.length);

    // Check Today group
    const todayGroup = result.find((g) => g.label === "Today");
    expect(todayGroup?.chats).toHaveLength(1);
    expect(todayGroup?.chats[0].title).toBe("Today chat");

    // Check Yesterday group
    const yesterdayGroup = result.find((g) => g.label === "Yesterday");
    expect(yesterdayGroup?.chats).toHaveLength(1);
    expect(yesterdayGroup?.chats[0].title).toBe("Yesterday chat");

    // Check 2d ago group
    const twoDaysGroup = result.find((g) => g.label === "2d ago");
    expect(twoDaysGroup?.chats).toHaveLength(1);
    expect(twoDaysGroup?.chats[0].title).toBe("2 days ago chat");

    // Check 3d ago group
    const threeDaysGroup = result.find((g) => g.label === "3d ago");
    expect(threeDaysGroup?.chats).toHaveLength(1);
    expect(threeDaysGroup?.chats[0].title).toBe("3 days ago chat");

    // Check This week group (should include 5)
    const thisWeekGroup = result.find((g) => g.label === "This week");
    expect(thisWeekGroup?.chats).toHaveLength(1);
    expect(thisWeekGroup?.chats.map((c) => c.title)).toContain(
      "5 days ago chat",
    );

    // Check This month group (should include 40 days ago)
    const thisMonthGroup = result.find((g) => g.label === "This month");
    expect(thisMonthGroup?.chats).toHaveLength(1);
    expect(thisMonthGroup?.chats[0].title).toBe("10 days ago chat");

    // Check Older group (should include 40 days ago)
    const olderGroup = result.find((g) => g.label === "Older");
    expect(olderGroup?.chats).toHaveLength(1);
    expect(olderGroup?.chats[0].title).toBe("40 days ago chat");
  });

  it("should include all chats in some group", () => {
    const chats: Chat[] = [
      createMockChat(0, "Today"),
      createMockChat(1, "Yesterday"),
      createMockChat(2, "2 days ago"),
      createMockChat(3, "3 days ago"),
      createMockChat(5, "5 days ago"),
      createMockChat(10, "10 days ago"),
      createMockChat(20, "20 days ago"),
      createMockChat(40, "40 days ago"),
      createMockChat(100, "100 days ago"),
    ];

    const result = groupChatsByDate(chats);

    // Count total chats across all groups
    const totalChatsInGroups = result.reduce(
      (sum, group) => sum + group.chats.length,
      0,
    );
    expect(totalChatsInGroups).toBe(chats.length);
  });

  it("should handle empty chat list", () => {
    const result = groupChatsByDate([]);
    expect(result).toHaveLength(0);
  });

  it("should filter out empty groups", () => {
    const chats: Chat[] = [
      createMockChat(0, "Today chat"),
      createMockChat(40, "Old chat"),
    ];

    const result = groupChatsByDate(chats);

    // Should only have Today and Older groups, not the empty ones in between
    expect(result).toHaveLength(2);
    expect(result.map((g) => g.label)).toEqual(["Today", "Older"]);
  });
});
