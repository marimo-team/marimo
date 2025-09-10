/* Copyright 2025 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type AgentSession,
  type AgentSessionId,
  type AgentSessionState,
  addSession,
  createSession,
  type ExternalAgentId,
  generateSessionId,
  getAgentConnectionCommand,
  getAgentDisplayName,
  getAllAgentIds,
  getSessionsByAgent,
  removeSession,
  truncateTitle,
  updateSessionAgentId,
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

  describe("generateSessionId", () => {
    it("should generate unique session IDs", () => {
      const id1 = generateSessionId();
      const id2 = generateSessionId();

      expect(id1).toMatch(/^session_\d+_[a-z0-9]+$/);
      expect(id2).toMatch(/^session_\d+_[a-z0-9]+$/);
      expect(id1).not.toBe(id2);
    });

    it("should include timestamp in session ID", () => {
      const id = generateSessionId();
      expect(id).toContain("session_1735689600000_"); // 2025-01-01T00:00:00Z timestamp
    });
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

  describe("createSession", () => {
    it("should create session with default title", () => {
      const session = createSession("claude");

      expect(session).toEqual({
        id: expect.stringMatching(/^session_\d+_[a-z0-9]+$/),
        agentId: "claude",
        title: "New claude session",
        createdAt: 1735689600000,
        lastUsedAt: 1735689600000,
      });
    });

    it("should create session with custom title from first message", () => {
      const session = createSession("gemini", "Hello, how are you today?");

      expect(session).toEqual({
        id: expect.stringMatching(/^session_\d+_[a-z0-9]+$/),
        agentId: "gemini",
        title: "Hello, how are yo...",
        createdAt: 1735689600000,
        lastUsedAt: 1735689600000,
      });
    });

    it("should trim whitespace from first message", () => {
      const session = createSession("claude", "  \n  Hello world  \t  ");
      expect(session.title).toBe("Hello world");
    });

    it("should handle empty first message", () => {
      const session = createSession("claude", "");
      expect(session.title).toBe("New claude session");
    });
  });

  describe("addSession", () => {
    it("should add session to empty state", () => {
      const initialState: AgentSessionState = {
        sessions: [],
        activeSessionId: null,
      };

      const session = createSession("claude");
      const newState = addSession(initialState, session);

      expect(newState).toEqual({
        sessions: [session],
        activeSessionId: session.id,
      });
    });

    it("should add session to existing sessions", () => {
      const existingSession = createSession("gemini");
      const initialState: AgentSessionState = {
        sessions: [existingSession],
        activeSessionId: existingSession.id,
      };

      const newSession = createSession("claude");
      const newState = addSession(initialState, newSession);

      expect(newState).toEqual({
        sessions: [existingSession, newSession],
        activeSessionId: newSession.id,
      });
    });

    it("should not mutate original state", () => {
      const initialState: AgentSessionState = {
        sessions: [],
        activeSessionId: null,
      };

      const session = createSession("claude");
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
        createSession("claude"),
        createSession("gemini"),
        createSession("claude"),
      ];
      state = {
        sessions,
        activeSessionId: sessions[1].id, // middle session is active
      };
    });

    it("should remove specified session", () => {
      const newState = removeSession(state, sessions[0].id);

      expect(newState.sessions).toHaveLength(2);
      expect(newState.sessions).not.toContain(sessions[0]);
      expect(newState.sessions).toContain(sessions[1]);
      expect(newState.sessions).toContain(sessions[2]);
    });

    it("should keep active session if not the one being removed", () => {
      const newState = removeSession(state, sessions[0].id);
      expect(newState.activeSessionId).toBe(sessions[1].id);
    });

    it("should set active session to last session when removing active session", () => {
      const newState = removeSession(state, sessions[1].id);
      expect(newState.activeSessionId).toBe(sessions[2].id);
    });

    it("should set active session to null when removing last session", () => {
      const singleSessionState: AgentSessionState = {
        sessions: [sessions[0]],
        activeSessionId: sessions[0].id,
      };

      const newState = removeSession(singleSessionState, sessions[0].id);
      expect(newState.sessions).toHaveLength(0);
      expect(newState.activeSessionId).toBe(null);
    });

    it("should handle removing non-existent session", () => {
      const fakeId = "fake_session_id" as AgentSessionId;
      const newState = removeSession(state, fakeId);

      expect(newState.sessions).toHaveLength(3);
      expect(newState.activeSessionId).toBe(sessions[1].id);
    });
  });

  describe("updateSessionTitle", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [
        createSession("claude", "Original title"),
        createSession("gemini", "Another title"),
      ];
      state = {
        sessions,
        activeSessionId: sessions[0].id,
      };
    });

    it("should update title of specified session", () => {
      const newTitle = "Updated title for session";
      const newState = updateSessionTitle(state, sessions[0].id, newTitle);

      expect(newState.sessions[0].title).toBe("Updated title for...");
      expect(newState.sessions[1].title).toBe("Another title");
    });

    it("should truncate long titles", () => {
      const longTitle = "This is a very long title that needs to be truncated";
      const newState = updateSessionTitle(state, sessions[0].id, longTitle);

      expect(newState.sessions[0].title).toBe("This is a very lo...");
      expect(newState.sessions[0].title.length).toBe(20);
    });

    it("should handle non-existent session ID", () => {
      const fakeId = "fake_session_id" as AgentSessionId;
      const newState = updateSessionTitle(state, fakeId, "New title");

      expect(newState.sessions[0].title).toBe("Original title");
      expect(newState.sessions[1].title).toBe("Another title");
    });

    it("should not mutate original state", () => {
      const originalTitle = sessions[0].title;
      updateSessionTitle(state, sessions[0].id, "New title");

      expect(sessions[0].title).toBe(originalTitle);
    });
  });

  describe("updateSessionLastUsed", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [createSession("claude"), createSession("gemini")];
      state = {
        sessions,
        activeSessionId: sessions[0].id,
      };
    });

    it("should update lastUsedAt timestamp", () => {
      const originalTimestamp = sessions[0].lastUsedAt;

      // Advance time by 1 hour
      vi.advanceTimersByTime(3600000);

      const newState = updateSessionLastUsed(state, sessions[0].id);

      expect(newState.sessions[0].lastUsedAt).toBe(1735693200000); // +1 hour
      expect(newState.sessions[0].lastUsedAt).not.toBe(originalTimestamp);
      expect(newState.sessions[1].lastUsedAt).toBe(originalTimestamp); // unchanged
    });

    it("should handle non-existent session ID", () => {
      const fakeId = "fake_session_id" as AgentSessionId;
      const originalTimestamp = sessions[0].lastUsedAt;

      vi.advanceTimersByTime(3600000);

      const newState = updateSessionLastUsed(state, fakeId);

      expect(newState.sessions[0].lastUsedAt).toBe(originalTimestamp);
      expect(newState.sessions[1].lastUsedAt).toBe(originalTimestamp);
    });
  });

  describe("updateSessionAgentId", () => {
    let sessions: AgentSession[];
    let state: AgentSessionState;

    beforeEach(() => {
      sessions = [createSession("claude"), createSession("gemini")];
      state = {
        sessions,
        activeSessionId: sessions[0].id,
      };
    });

    it("should update agentSessionId and lastUsedAt", () => {
      const originalTimestamp = sessions[0].lastUsedAt;
      const agentSessionId = "agent_session_123";

      // Advance time by 1 hour
      vi.advanceTimersByTime(3600000);

      const newState = updateSessionAgentId(
        state,
        sessions[0].id,
        agentSessionId,
      );

      expect(newState.sessions[0].agentSessionId).toBe(agentSessionId);
      expect(newState.sessions[0].lastUsedAt).toBe(1735693200000); // +1 hour
      expect(newState.sessions[0].lastUsedAt).not.toBe(originalTimestamp);
      expect(newState.sessions[1].agentSessionId).toBeUndefined(); // unchanged
    });

    it("should handle non-existent session ID", () => {
      const fakeId = "fake_session_id" as AgentSessionId;
      const agentSessionId = "agent_session_123";

      const newState = updateSessionAgentId(state, fakeId, agentSessionId);

      expect(newState.sessions[0].agentSessionId).toBeUndefined();
      expect(newState.sessions[1].agentSessionId).toBeUndefined();
    });

    it("should not mutate original state", () => {
      const originalSession = sessions[0];
      const agentSessionId = "agent_session_123";

      updateSessionAgentId(state, sessions[0].id, agentSessionId);

      expect(originalSession.agentSessionId).toBeUndefined();
    });
  });

  describe("getSessionsByAgent", () => {
    let sessions: AgentSession[];

    beforeEach(() => {
      // Create sessions with different timestamps for sorting test
      vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));
      const session1 = createSession("claude", "First claude");

      vi.setSystemTime(new Date("2025-01-01T01:00:00Z"));
      const session2 = createSession("gemini", "First gemini");

      vi.setSystemTime(new Date("2025-01-01T02:00:00Z"));
      const session3 = createSession("claude", "Second claude");

      vi.setSystemTime(new Date("2025-01-01T03:00:00Z"));
      const session4 = createSession("claude", "Third claude");

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
