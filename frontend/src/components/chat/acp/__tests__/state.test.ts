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

      const session = { agentId: "claude" };
      const newState = addSession(initialState, session);

      expect(newState).toEqual({
        sessions: [session],
        activeTabId: session.tabId,
      });
    });

    it("should add session to existing sessions", () => {
      const existingSession = { agentId: "gemini" };
      const initialState: AgentSessionState = {
        sessions: [existingSession],
        activeTabId: existingSession.tabId as TabId,
      };

      const newSession = { agentId: "claude" };
      const newState = addSession(initialState, newSession);

      expect(newState).toEqual({
        sessions: [existingSession, newSession],
        activeTabId: newSession.tabId as TabId,
      });
    });

    it("should not mutate original state", () => {
      const initialState: AgentSessionState = {
        sessions: [],
        activeTabId: null,
      };

      const session = { agentId: "claude" };
      const newState = addSession(initialState, session);

      expect(initialState.sessions).toHaveLength(0);
      expect(newState.sessions).toHaveLength(1);
    });
  });

  describe("removeSession", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [
        { agentId: "claude" },
        { agentId: "gemini" },
        { agentId: "claude" },
      ];
      state = {
        sessions,
        activeTabId: sessions[1].tabId, // middle session is active
      };
    });

    it("should remove specified session", () => {
      const newState = removeSession(state, sessions[0].tabId);

      expect(newState.sessions).toHaveLength(2);
      expect(newState.sessions).not.toContain(sessions[0]);
      expect(newState.sessions).toContain(sessions[1]);
      expect(newState.sessions).toContain(sessions[2]);
    });

    it("should keep active session if not the one being removed", () => {
      const newState = removeSession(state, sessions[0].tabId);
      expect(newState.activeTabId).toBe(sessions[1].tabId);
    });

    it("should set active session to last session when removing active session", () => {
      const newState = removeSession(state, sessions[1].tabId);
      expect(newState.activeTabId).toBe(sessions[2].tabId);
    });

    it("should set active session to null when removing last session", () => {
      const singleSessionState: AgentSessionState = {
        sessions: [sessions[0]],
        activeTabId: sessions[0].tabId,
      };

      const newState = removeSession(singleSessionState, sessions[0].tabId);
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
        { agentId: "claude", firstMessage: "Original title" },
        { agentId: "gemini", firstMessage: "Another title" },
      ];
      state = {
        sessions,
        activeTabId: sessions[0].tabId,
      };
    });

    it("should update title of specified session", () => {
      const newTitle = "Updated title for session";
      const newState = updateSessionTitle(state, sessions[0].tabId, newTitle);

      expect(newState.sessions[0].title).toBe("Updated title for...");
      expect(newState.sessions[1].title).toBe("Another title");
    });

    it("should truncate long titles", () => {
      const longTitle = "This is a very long title that needs to be truncated";
      const newState = updateSessionTitle(state, sessions[0].tabId, longTitle);

      expect(newState.sessions[0].title).toBe("This is a very lo...");
      expect(newState.sessions[0].title.length).toBe(20);
    });

    it("should handle non-existent session ID", () => {
      const fakeId = "fake_session_id" as TabId;
      const newState = updateSessionTitle(state, fakeId, "New title");

      expect(newState.sessions[0].title).toBe("Original title");
      expect(newState.sessions[1].title).toBe("Another title");
    });

    it("should not mutate original state", () => {
      const originalTitle = sessions[0].title;
      updateSessionTitle(state, sessions[0].tabId, "New title");

      expect(sessions[0].title).toBe(originalTitle);
    });
  });

  describe("updateSessionLastUsed", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [{ agentId: "claude" }, { agentId: "gemini" }];
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

      expect(newState.sessions[0].lastUsedAt).toBe(1735693200000); // +1 hour
      expect(newState.sessions[0].lastUsedAt).not.toBe(originalTimestamp);
      expect(newState.sessions[1].lastUsedAt).toBe(originalTimestamp); // unchanged
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
      sessions = [{ agentId: "claude" }, { agentId: "gemini" }];
      state = {
        sessions,
        activeTabId: sessions[0].tabId,
      };
    });

    it("should update externalAgentSessionId and lastUsedAt", () => {
      const originalTimestamp = sessions[0].lastUsedAt;
      const agentSessionId = "agent_session_123" as any;

      // Advance time by 1 hour
      vi.advanceTimersByTime(3600000);

      const newState = updateSessionExternalAgentSessionId(
        state,
        sessions[0].tabId,
        agentSessionId,
      );

      expect(newState.sessions[0].externalAgentSessionId).toBe(agentSessionId);
      expect(newState.sessions[0].lastUsedAt).toBe(1735693200000); // +1 hour
      expect(newState.sessions[0].lastUsedAt).not.toBe(originalTimestamp);
      expect(newState.sessions[1].externalAgentSessionId).toBeUndefined(); // unchanged
    });

    it("should handle non-existent session ID", () => {
      const fakeId = "fake_session_id" as TabId;
      const agentSessionId = "agent_session_123" as any;

      const newState = updateSessionExternalAgentSessionId(
        state,
        fakeId,
        agentSessionId,
      );

      expect(newState.sessions[0].externalAgentSessionId).toBeUndefined();
      expect(newState.sessions[1].externalAgentSessionId).toBeUndefined();
    });

    it("should not mutate original state", () => {
      const originalSession = sessions[0];
      const agentSessionId = "agent_session_123" as any;

      updateSessionExternalAgentSessionId(
        state,
        sessions[0].tabId,
        agentSessionId,
      );

      expect(originalSession.externalAgentSessionId).toBeUndefined();
    });
  });

  describe("getSessionsByAgent", () => {
    let sessions: AgentSession[];

    beforeEach(() => {
      // Create sessions with different timestamps for sorting test
      vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));
      const session1 = { agentId: "claude", firstMessage: "First claude" };

      vi.setSystemTime(new Date("2025-01-01T01:00:00Z"));
      const session2 = { agentId: "gemini", firstMessage: "First gemini" };

      vi.setSystemTime(new Date("2025-01-01T02:00:00Z"));
      const session3 = { agentId: "claude", firstMessage: "Second claude" };

      vi.setSystemTime(new Date("2025-01-01T03:00:00Z"));
      const session4 = { agentId: "claude", firstMessage: "Third claude" };

      sessions = [session1, session2, session3, session4];
    });

    it("should filter sessions by agent", () => {
      const claudeSessions = getSessionsByAgent(sessions, "claude");

      expect(claudeSessions).toHaveLength(3);
      expect(claudeSessions.every((s) => s.agentId === "claude")).toBe(true);
    });

    it("should sort sessions by lastUsedAt in descending order", () => {
      const claudeSessions = getSessionsByAgent(sessions, "claude");

      expect(claudeSessions[0].title).toBe("Third claude");
      expect(claudeSessions[1].title).toBe("Second claude");
      expect(claudeSessions[2].title).toBe("First claude");
    });

    it("should return empty array for non-existent agent", () => {
      const nonExistentSessions = getSessionsByAgent(
        sessions,
        "nonexistent" as ExternalAgentId,
      );
      expect(nonExistentSessions).toHaveLength(0);
    });

    it("should return empty array for empty sessions list", () => {
      const result = getSessionsByAgent([], "claude");
      expect(result).toHaveLength(0);
    });
  });

  describe("getAllAgentIds", () => {
    it("should return all available agent IDs", () => {
      const agentIds = getAllAgentIds();
      expect(agentIds).toEqual(["claude", "gemini"]);
    });

    it("should return array with correct length", () => {
      const agentIds = getAllAgentIds();
      expect(agentIds).toHaveLength(2);
    });
  });

  describe("getAgentDisplayName", () => {
    it("should capitalize agent names", () => {
      expect(getAgentDisplayName("claude")).toBe("Claude");
      expect(getAgentDisplayName("gemini")).toBe("Gemini");
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
