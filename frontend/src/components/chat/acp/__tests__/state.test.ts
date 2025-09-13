/* Copyright 2025 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type AgentSession,
  type AgentSessionState,
  addSession,
  type ExternalAgentId,
  getAgentConnectionCommand,
  getAgentDisplayName,
  getAllAgentIds,
  getSessionsByAgent,
  removeSession,
  type TabId,
  truncateTitle,
  updateSessionExternalAgentSessionId,
  updateSessionLastUsed,
  updateSessionTitle,
} from "../state";
import type { ExternalAgentSessionId } from "../types";

describe("state utility functions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock Date.now for consistent testing
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("truncateTitle", () => {
    it("should not truncate short titles", () => {
      expect(truncateTitle("Hello")).toBe("Hello");
      expect(truncateTitle("Test message")).toBe("Test message");
    });

    it("should truncate long titles to default 20 characters", () => {
      const longTitle = "This is a very long title that should be truncated";
      const result = truncateTitle(longTitle);
      expect(result).toBe("This is a very lo...");
      expect(result.length).toBe(20);
    });

    it("should truncate to custom max length", () => {
      const longTitle = "This is a long title";
      const result = truncateTitle(longTitle, 10);
      expect(result).toBe("This is...");
      expect(result.length).toBe(10);
    });

    it("should handle empty strings", () => {
      expect(truncateTitle("")).toBe("");
    });

    it("should handle titles exactly at max length", () => {
      const exactTitle = "Exactly twenty chars";
      expect(exactTitle.length).toBe(20);
      expect(truncateTitle(exactTitle)).toBe(exactTitle);
    });
  });

  describe("addSession", () => {
    it("should add session to empty state", () => {
      const initialState: AgentSessionState = {
        sessions: [],
        activeTabId: null,
      };

      const session = { agentId: "claude" as ExternalAgentId };
      const newState = addSession(initialState, session);

      // Remove the dynamic tabId for snapshot comparison
      const { tabId, ...sessionWithoutId } = newState.sessions[0];
      expect({
        ...newState,
        sessions: [sessionWithoutId],
        activeTabId: "[DYNAMIC_TAB_ID]",
      }).toMatchInlineSnapshot(`
        {
          "activeTabId": "[DYNAMIC_TAB_ID]",
          "sessions": [
            {
              "agentId": "claude",
              "createdAt": 1735689600000,
              "externalAgentSessionId": null,
              "lastUsedAt": 1735689600000,
              "title": "New claude session",
            },
          ],
        }
      `);
      expect(newState.activeTabId).toBe(newState.sessions[0].tabId);
    });

    it("should add session when no existing session for different agent", () => {
      const existingSession: AgentSession = {
        agentId: "gemini",
        tabId: "tab_existing" as TabId,
        title: "Existing gemini session",
        createdAt: 1735689600000,
        lastUsedAt: 1735689600000,
        externalAgentSessionId: null,
      };
      const initialState: AgentSessionState = {
        sessions: [existingSession],
        activeTabId: existingSession.tabId,
      };

      const newSession = { agentId: "claude" as ExternalAgentId };
      const newState = addSession(initialState, newSession);

      // Remove dynamic tabId for snapshot
      const { tabId, ...sessionWithoutId } = newState.sessions[0];
      expect({
        ...newState,
        sessions: [sessionWithoutId],
        activeTabId: "[DYNAMIC_TAB_ID]",
      }).toMatchInlineSnapshot(`
        {
          "activeTabId": "[DYNAMIC_TAB_ID]",
          "sessions": [
            {
              "agentId": "claude",
              "createdAt": 1735689600000,
              "externalAgentSessionId": null,
              "lastUsedAt": 1735689600000,
              "title": "New claude session",
            },
          ],
        }
      `);
    });

    it("should replace existing session for same agent (single session support)", () => {
      const existingSession: AgentSession = {
        agentId: "claude",
        tabId: "tab_existing" as TabId,
        title: "Existing claude session",
        createdAt: 1735689600000,
        lastUsedAt: 1735689600000,
        externalAgentSessionId: null,
      };
      const initialState: AgentSessionState = {
        sessions: [existingSession],
        activeTabId: existingSession.tabId,
      };

      const newSession = {
        agentId: "claude" as ExternalAgentId,
        firstMessage: "Hello",
      };
      const newState = addSession(initialState, newSession);

      expect(newState).toMatchInlineSnapshot(`
        {
          "activeTabId": "tab_existing",
          "sessions": [
            {
              "agentId": "claude",
              "createdAt": 1735689600000,
              "externalAgentSessionId": null,
              "lastUsedAt": 1735689600000,
              "tabId": "tab_existing",
              "title": "Hello",
            },
          ],
        }
      `);
    });

    it("should not mutate original state", () => {
      const initialState: AgentSessionState = {
        sessions: [],
        activeTabId: null,
      };

      const newState = addSession(initialState, { agentId: "claude" });

      expect(initialState.sessions).toHaveLength(0);
      expect(newState.sessions).toHaveLength(1);
    });
  });

  describe("removeSession", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [
        {
          agentId: "claude",
          tabId: "tab_1" as TabId,
          title: "Claude session 1",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
        {
          agentId: "gemini",
          tabId: "tab_2" as TabId,
          title: "Gemini session",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
        {
          agentId: "claude",
          tabId: "tab_3" as TabId,
          title: "Claude session 2",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
      ];
      state = {
        sessions,
        activeTabId: sessions[1].tabId, // middle session is active
      };
    });

    it("should remove specified session", () => {
      const newState = removeSession(state, sessions[1].tabId);

      expect(newState).toMatchInlineSnapshot(`
        {
          "activeTabId": "tab_3",
          "sessions": [
            {
              "agentId": "claude",
              "createdAt": 1735689600000,
              "externalAgentSessionId": null,
              "lastUsedAt": 1735689600000,
              "tabId": "tab_1",
              "title": "Claude session 1",
            },
            {
              "agentId": "claude",
              "createdAt": 1735689600000,
              "externalAgentSessionId": null,
              "lastUsedAt": 1735689600000,
              "tabId": "tab_3",
              "title": "Claude session 2",
            },
          ],
        }
      `);
    });

    it("should keep active session if not the one being removed", () => {
      const newState = removeSession(state, sessions[1].tabId);
      expect(newState.activeTabId).toMatchInlineSnapshot(`"tab_3"`);
    });

    it("should set active session to last session when removing active session", () => {
      const newState = removeSession(state, sessions[1].tabId);
      expect(newState.activeTabId).toMatchInlineSnapshot(`"tab_3"`);
    });

    it("should set active session to null when removing last session", () => {
      const singleSession: AgentSession = {
        agentId: "claude",
        tabId: "tab_single" as TabId,
        title: "Single session",
        createdAt: 1735689600000,
        lastUsedAt: 1735689600000,
        externalAgentSessionId: null,
      };
      const singleSessionState: AgentSessionState = {
        sessions: [singleSession],
        activeTabId: singleSession.tabId,
      };

      const newState = removeSession(singleSessionState, singleSession.tabId);
      expect(newState.sessions).toHaveLength(0);
      expect(newState.activeTabId).toBe(null);
    });

    it("should handle removing non-existent session", () => {
      const fakeId = "fake_session_id" as TabId;
      const newState = removeSession(state, fakeId);

      expect(newState.sessions).toHaveLength(3);
      expect(newState.activeTabId).toBe(sessions[1].tabId);
    });
  });

  describe("updateSessionTitle", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [
        {
          agentId: "claude",
          tabId: "tab_1" as TabId,
          title: "Original title",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
        {
          agentId: "gemini",
          tabId: "tab_2" as TabId,
          title: "Another title",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
      ];
      state = {
        sessions,
        activeTabId: sessions[0].tabId,
      };
    });

    it("should update title of specified session", () => {
      const newTitle = "Updated title for session";
      const newState = updateSessionTitle(state, newTitle);

      expect(newState.sessions.map((s) => s.title)).toMatchInlineSnapshot(`
        [
          "Updated title for...",
          "Another title",
        ]
      `);
    });

    it("should truncate long titles", () => {
      const longTitle = "This is a very long title that needs to be truncated";
      const newState = updateSessionTitle(state, longTitle);

      expect({
        title: newState.sessions[0].title,
        length: newState.sessions[0].title.length,
      }).toMatchInlineSnapshot(`
        {
          "length": 20,
          "title": "This is a very lo...",
        }
      `);
    });

    it("should not mutate original state", () => {
      const originalTitle = sessions[0].title;
      updateSessionTitle(state, "New title");

      expect(sessions[0].title).toBe(originalTitle);
    });
  });

  describe("updateSessionLastUsed", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [
        {
          agentId: "claude",
          tabId: "tab_1" as TabId,
          title: "Claude session",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
        {
          agentId: "gemini",
          tabId: "tab_2" as TabId,
          title: "Gemini session",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
      ];
      state = {
        sessions,
        activeTabId: sessions[0].tabId,
      };
    });

    it("should update lastUsedAt timestamp", () => {
      const originalTimestamp = sessions[0].lastUsedAt;

      // Advance time by 1 hour
      vi.advanceTimersByTime(3600000);

      const newState = updateSessionLastUsed(state, sessions[0].tabId);

      expect({
        updatedTimestamp: newState.sessions[0].lastUsedAt,
        unchangedTimestamp: newState.sessions[1].lastUsedAt,
        timestampChanged: newState.sessions[0].lastUsedAt !== originalTimestamp,
      }).toMatchInlineSnapshot(`
        {
          "timestampChanged": true,
          "unchangedTimestamp": 1735689600000,
          "updatedTimestamp": 1735693200000,
        }
      `);
    });

    it("should handle non-existent session ID", () => {
      const fakeId = "fake_session_id" as TabId;
      const originalTimestamp = sessions[0].lastUsedAt;

      vi.advanceTimersByTime(3600000);

      const newState = updateSessionLastUsed(state, fakeId);

      expect(newState.sessions[0].lastUsedAt).toBe(originalTimestamp);
      expect(newState.sessions[1].lastUsedAt).toBe(originalTimestamp);
    });
  });

  describe("updateSessionExternalAgentSessionId", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [
        {
          agentId: "claude",
          tabId: "tab_1" as TabId,
          title: "Claude session",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
        {
          agentId: "gemini",
          tabId: "tab_2" as TabId,
          title: "Gemini session",
          createdAt: 1735689600000,
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
      ];
      state = {
        sessions,
        activeTabId: sessions[0].tabId,
      };
    });

    it("should update externalAgentSessionId and lastUsedAt", () => {
      const originalTimestamp = sessions[0].lastUsedAt;
      const agentSessionId = "agent_session_123" as ExternalAgentSessionId;

      // Advance time by 1 hour
      vi.advanceTimersByTime(3600000);

      const newState = updateSessionExternalAgentSessionId(
        state,
        agentSessionId,
      );

      expect({
        updatedSession: {
          externalAgentSessionId: newState.sessions[0].externalAgentSessionId,
          lastUsedAt: newState.sessions[0].lastUsedAt,
        },
        unchangedSession: {
          externalAgentSessionId: newState.sessions[1].externalAgentSessionId,
        },
        timestampChanged: newState.sessions[0].lastUsedAt !== originalTimestamp,
      }).toMatchInlineSnapshot(`
        {
          "timestampChanged": true,
          "unchangedSession": {
            "externalAgentSessionId": null,
          },
          "updatedSession": {
            "externalAgentSessionId": "agent_session_123",
            "lastUsedAt": 1735693200000,
          },
        }
      `);
    });

    it("should not mutate original state", () => {
      const originalSession = sessions[0];
      const agentSessionId = "agent_session_123" as ExternalAgentSessionId;

      updateSessionExternalAgentSessionId(state, agentSessionId);

      expect(originalSession.externalAgentSessionId).toBe(null);
    });
  });

  describe("getSessionsByAgent", () => {
    let sessions: AgentSession[];

    beforeEach(() => {
      // Create sessions with different timestamps for sorting test
      sessions = [
        {
          agentId: "claude",
          tabId: "tab_1" as TabId,
          title: "First claude",
          createdAt: 1735689600000, // 2025-01-01T00:00:00Z
          lastUsedAt: 1735689600000,
          externalAgentSessionId: null,
        },
        {
          agentId: "gemini",
          tabId: "tab_2" as TabId,
          title: "First gemini",
          createdAt: 1735693200000, // 2025-01-01T01:00:00Z
          lastUsedAt: 1735693200000,
          externalAgentSessionId: null,
        },
        {
          agentId: "claude",
          tabId: "tab_3" as TabId,
          title: "Second claude",
          createdAt: 1735696800000, // 2025-01-01T02:00:00Z
          lastUsedAt: 1735696800000,
          externalAgentSessionId: null,
        },
        {
          agentId: "claude",
          tabId: "tab_4" as TabId,
          title: "Third claude",
          createdAt: 1735700400000, // 2025-01-01T03:00:00Z
          lastUsedAt: 1735700400000,
          externalAgentSessionId: null,
        },
      ];
    });

    it("should filter sessions by agent", () => {
      const claudeSessions = getSessionsByAgent(sessions, "claude");

      expect({
        length: claudeSessions.length,
        allClaude: claudeSessions.every((s) => s.agentId === "claude"),
        agentIds: claudeSessions.map((s) => s.agentId),
      }).toMatchInlineSnapshot(`
        {
          "agentIds": [
            "claude",
            "claude",
            "claude",
          ],
          "allClaude": true,
          "length": 3,
        }
      `);
    });

    it("should sort sessions by lastUsedAt in descending order", () => {
      const claudeSessions = getSessionsByAgent(sessions, "claude");

      expect(claudeSessions.map((s) => s.title)).toMatchInlineSnapshot(`
        [
          "Third claude",
          "Second claude",
          "First claude",
        ]
      `);
    });

    it("should return empty array for non-existent agent", () => {
      const nonExistentSessions = getSessionsByAgent(
        sessions,
        "nonexistent" as ExternalAgentId,
      );
      expect(nonExistentSessions).toMatchInlineSnapshot("[]");
    });

    it("should return empty array for empty sessions list", () => {
      const result = getSessionsByAgent([], "claude");
      expect(result).toMatchInlineSnapshot("[]");
    });
  });

  describe("getAllAgentIds", () => {
    it("should return all available agent IDs", () => {
      const agentIds = getAllAgentIds();
      expect(agentIds).toMatchInlineSnapshot(`
        [
          "claude",
          "gemini",
        ]
      `);
    });
  });

  describe("getAgentDisplayName", () => {
    it("should capitalize agent names", () => {
      expect({
        claude: getAgentDisplayName("claude"),
        gemini: getAgentDisplayName("gemini"),
      }).toMatchInlineSnapshot(`
        {
          "claude": "Claude",
          "gemini": "Gemini",
        }
      `);
    });
  });

  describe("getAgentConnectionCommand", () => {
    it("should return correct command for claude", () => {
      expect(getAgentConnectionCommand("claude")).toMatchInlineSnapshot(`
        "npx supergateway --stdio\\
          "npx @zed-industries/claude-code-acp" \\
           --outputTransport ws --port 3017 "
      `);
    });

    it("should return correct command for gemini", () => {
      expect(getAgentConnectionCommand("gemini")).toMatchInlineSnapshot(`
        "npx supergateway --stdio\\
          "npx @google/gemini-cli --experimental-acp" \\
           --outputTransport ws --port 3019 "
      `);
    });
  });
});
