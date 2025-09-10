/* Copyright 2025 Marimo. All rights reserved. */

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { capitalize } from "lodash-es";
import type { TypedString } from "@/utils/typed";

// Types
export type AgentSessionId = TypedString<"AgentSessionId">;
export type ExternalAgentId = "claude" | "gemini";

export interface AgentSession {
  id: AgentSessionId;
  agentId: ExternalAgentId;
  title: string;
  createdAt: number;
  lastUsedAt: number;
  // Store the actual agent session ID for resumption
  agentSessionId?: string;
}

export interface AgentSessionState {
  sessions: AgentSession[];
  activeSessionId: AgentSessionId | null;
}

// Constants
const STORAGE_KEY = "marimo:acp:sessions:v1";

// Atoms
export const agentSessionStateAtom = atomWithStorage<AgentSessionState>(
  STORAGE_KEY,
  {
    sessions: [],
    activeSessionId: null,
  },
);

export const activeSessionAtom = atom(
  (get) => {
    const state = get(agentSessionStateAtom);
    if (!state.activeSessionId) {
      return null;
    }
    return (
      state.sessions.find((session) => session.id === state.activeSessionId) ||
      null
    );
  },
  (get, set, sessionId: AgentSessionId | null) => {
    set(agentSessionStateAtom, (prev) => ({
      ...prev,
      activeSessionId: sessionId,
    }));
  },
);

// Utilities
export function generateSessionId(): AgentSessionId {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` as AgentSessionId;
}

export function truncateTitle(title: string, maxLength: number = 20): string {
  if (title.length <= maxLength) {
    return title;
  }
  return `${title.slice(0, maxLength - 3)}...`;
}

export function createSession(
  agentId: ExternalAgentId,
  firstMessage?: string,
): AgentSession {
  const now = Date.now();
  const title = firstMessage
    ? truncateTitle(firstMessage.trim())
    : `New ${agentId} session`;

  return {
    id: generateSessionId(),
    agentId,
    title,
    createdAt: now,
    lastUsedAt: now,
  };
}

export function addSession(
  state: AgentSessionState,
  session: AgentSession,
): AgentSessionState {
  return {
    ...state,
    sessions: [...state.sessions, session],
    activeSessionId: session.id,
  };
}

export function removeSession(
  state: AgentSessionState,
  sessionId: AgentSessionId,
): AgentSessionState {
  const filteredSessions = state.sessions.filter((s) => s.id !== sessionId);
  const newActiveSessionId =
    state.activeSessionId === sessionId
      ? filteredSessions.length > 0
        ? filteredSessions[filteredSessions.length - 1].id
        : null
      : state.activeSessionId;

  return {
    sessions: filteredSessions,
    activeSessionId: newActiveSessionId,
  };
}

export function updateSessionTitle(
  state: AgentSessionState,
  sessionId: AgentSessionId,
  title: string,
): AgentSessionState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.id === sessionId
        ? { ...session, title: truncateTitle(title) }
        : session,
    ),
  };
}

export function updateSessionLastUsed(
  state: AgentSessionState,
  sessionId: AgentSessionId,
): AgentSessionState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.id === sessionId
        ? { ...session, lastUsedAt: Date.now() }
        : session,
    ),
  };
}

export function updateSessionAgentId(
  state: AgentSessionState,
  sessionId: AgentSessionId,
  agentSessionId: string,
): AgentSessionState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.id === sessionId
        ? { ...session, agentSessionId, lastUsedAt: Date.now() }
        : session,
    ),
  };
}

export function getSessionsByAgent(
  sessions: AgentSession[],
  agentId: ExternalAgentId,
): AgentSession[] {
  return sessions
    .filter((session) => session.agentId === agentId)
    .sort((a, b) => b.lastUsedAt - a.lastUsedAt);
}

export function getAllAgentIds(): ExternalAgentId[] {
  return ["claude", "gemini"];
}

export function getAgentDisplayName(agentId: ExternalAgentId): string {
  return capitalize(agentId);
}

export function getAgentWebSocketUrl(agentId: ExternalAgentId): string {
  switch (agentId) {
    case "claude":
      return "ws://localhost:8000/message";
    case "gemini":
      return "ws://localhost:8001/message"; // Assuming different port for Gemini
    default:
      throw new Error(`Unknown agent: ${agentId}`);
  }
}
