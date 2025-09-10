/* Copyright 2025 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  type AgentSessionState,
  activeSessionAtom,
  addSession,
  agentSessionStateAtom,
  createSession,
} from "../state";

describe("Jotai atoms", () => {
  let store: ReturnType<typeof createStore>;

  beforeEach(() => {
    store = createStore();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2025-01-01T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("agentSessionStateAtom", () => {
    it("should have initial empty state", () => {
      const state = store.get(agentSessionStateAtom);
      expect(state).toEqual({
        sessions: [],
        activeSessionId: null,
      });
    });

    it("should update state when set", () => {
      const session = createSession("claude", "Test message");
      const newState: AgentSessionState = {
        sessions: [session],
        activeSessionId: session.id,
      };

      store.set(agentSessionStateAtom, newState);
      const state = store.get(agentSessionStateAtom);

      expect(state).toEqual(newState);
    });
  });

  describe("activeSessionAtom", () => {
    it("should return null when no active session", () => {
      const activeSession = store.get(activeSessionAtom);
      expect(activeSession).toBe(null);
    });

    it("should return active session when available", () => {
      const session = createSession("gemini", "Hello world");
      const state = addSession(
        {
          sessions: [],
          activeSessionId: null,
        },
        session,
      );

      store.set(agentSessionStateAtom, state);
      const activeSession = store.get(activeSessionAtom);

      expect(activeSession).toEqual(session);
    });

    it("should return null when activeSessionId doesn't match any session", () => {
      const session = createSession("claude");
      const state: AgentSessionState = {
        sessions: [session],
        activeSessionId: "non_existent_id" as any,
      };

      store.set(agentSessionStateAtom, state);
      const activeSession = store.get(activeSessionAtom);

      expect(activeSession).toBe(null);
    });

    it("should update activeSessionId when set", () => {
      const session1 = createSession("claude");
      const session2 = createSession("gemini");
      const state: AgentSessionState = {
        sessions: [session1, session2],
        activeSessionId: session1.id,
      };

      store.set(agentSessionStateAtom, state);

      // Set new active session
      store.set(activeSessionAtom, session2.id);

      const updatedState = store.get(agentSessionStateAtom);
      expect(updatedState.activeSessionId).toBe(session2.id);

      const activeSession = store.get(activeSessionAtom);
      expect(activeSession).toEqual(session2);
    });

    it("should set activeSessionId to null when passed null", () => {
      const session = createSession("claude");
      const state = addSession(
        {
          sessions: [],
          activeSessionId: null,
        },
        session,
      );

      store.set(agentSessionStateAtom, state);
      expect(store.get(activeSessionAtom)).toEqual(session);

      // Set to null
      store.set(activeSessionAtom, null);

      const updatedState = store.get(agentSessionStateAtom);
      expect(updatedState.activeSessionId).toBe(null);
      expect(store.get(activeSessionAtom)).toBe(null);
    });
  });
});
