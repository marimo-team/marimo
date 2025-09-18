/* Copyright 2024 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { addSession, agentSessionStateAtom, selectedTabAtom } from "../state";

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
        activeTabId: null,
      });
    });
  });

  describe("activeSessionAtom", () => {
    it("should return null when no active session", () => {
      const activeSession = store.get(selectedTabAtom);
      expect(activeSession).toBe(null);
    });

    it("should return active session when available", () => {
      const state = addSession(
        {
          sessions: [],
          activeTabId: null,
        },
        { agentId: "gemini" },
      );

      store.set(agentSessionStateAtom, state);
      const activeSession = store.get(selectedTabAtom);

      expect(activeSession).toEqual(
        expect.objectContaining({
          agentId: "gemini",
          title: "New gemini session",
        }),
      );
    });
  });
});
