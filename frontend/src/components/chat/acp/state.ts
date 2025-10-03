/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { capitalize } from "lodash-es";
import type { TypedString } from "@/utils/typed";
import { generateUUID } from "@/utils/uuid";
import type { ExternalAgentSessionId, SessionSupportType } from "./types";

// Types
export type TabId = TypedString<"TabId">;
export type ExternalAgentId = "claude" | "gemini";

// No agents support loading sessions, so we limit to 1, otherwise
// this is confusing to the user when switching between sessions
const MAX_SESSIONS = 1;

export interface AgentSession {
  tabId: TabId;
  agentId: ExternalAgentId;
  title: string;
  createdAt: number;
  lastUsedAt: number;
  // Store the actual agent session ID for resumption
  externalAgentSessionId: ExternalAgentSessionId | null;
}

export interface AgentSessionState {
  sessions: AgentSession[];
  activeTabId: TabId | null;
}

// Constants
const STORAGE_KEY = "marimo:acp:sessions:v1";

// Atoms
export const agentSessionStateAtom = atomWithStorage<AgentSessionState>(
  STORAGE_KEY,
  {
    sessions: [],
    activeTabId: null,
  },
);

export const selectedTabAtom = atom(
  (get) => {
    const state = get(agentSessionStateAtom);
    if (!state.activeTabId) {
      return null;
    }
    return (
      state.sessions.find((session) => session.tabId === state.activeTabId) ||
      null
    );
  },
  (_get, set, activeTabId: TabId | null) => {
    set(agentSessionStateAtom, (prev) => ({
      ...prev,
      activeTabId: activeTabId,
    }));
  },
);

// Utilities
function generateTabId(): TabId {
  // Our tab ID for internal session management
  return `tab_${generateUUID()}` as TabId;
}

export function truncateTitle(title: string, maxLength = 20): string {
  if (title.length <= maxLength) {
    return title;
  }
  return `${title.slice(0, maxLength - 3)}...`;
}

export function addSession(
  state: AgentSessionState,
  session: {
    agentId: ExternalAgentId;
    firstMessage?: string;
  },
): AgentSessionState {
  const sessionSupport = getAgentSessionSupport(session.agentId);

  const now = Date.now();
  const title = session.firstMessage
    ? truncateTitle(session.firstMessage.trim())
    : `New ${session.agentId} session`;
  const tabId = generateTabId();

  if (sessionSupport === "single") {
    // For single session agents, replace any existing session for this agent
    const existingSessions = state.sessions.filter(
      (s) => s.agentId === session.agentId,
    );
    const otherSessions = state.sessions.filter(
      (s) => s.agentId !== session.agentId,
    );

    if (existingSessions.length > 0) {
      // Replace the existing session (overwrite it)
      const existingSession = existingSessions[0];
      const updatedSession: AgentSession = {
        agentId: session.agentId,
        title,
        createdAt: now,
        lastUsedAt: now,
        tabId: existingSession.tabId, // Keep the same ID to maintain tab reference
        externalAgentSessionId: null, // Clear the external session ID
      };

      return {
        ...state,
        sessions: [...otherSessions.slice(0, MAX_SESSIONS - 1), updatedSession],
        activeTabId: updatedSession.tabId,
      };
    }
  }

  // For multiple session agents or when no existing session exists
  return {
    ...state,
    sessions: [
      ...state.sessions.slice(0, MAX_SESSIONS - 1),
      {
        agentId: session.agentId,
        tabId,
        title,
        createdAt: now,
        lastUsedAt: now,
        externalAgentSessionId: null,
      },
    ],
    activeTabId: tabId,
  };
}

export function removeSession(
  state: AgentSessionState,
  sessionId: TabId,
): AgentSessionState {
  const filteredSessions = state.sessions.filter((s) => s.tabId !== sessionId);
  const newActiveTabId =
    state.activeTabId === sessionId
      ? filteredSessions.length > 0
        ? filteredSessions[filteredSessions.length - 1].tabId
        : null
      : state.activeTabId;

  return {
    sessions: filteredSessions,
    activeTabId: newActiveTabId,
  };
}

export function updateSessionTitle(
  state: AgentSessionState,
  title: string,
): AgentSessionState {
  const selectedTab = state.activeTabId;
  if (!selectedTab) {
    return state;
  }
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.tabId === selectedTab
        ? { ...session, title: truncateTitle(title) }
        : session,
    ),
  };
}

export function updateSessionLastUsed(
  state: AgentSessionState,
  sessionId: TabId,
): AgentSessionState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.tabId === sessionId
        ? { ...session, lastUsedAt: Date.now() }
        : session,
    ),
  };
}

/**
 * Update the sessionId for the current;y selected tab
 */
export function updateSessionExternalAgentSessionId(
  state: AgentSessionState,
  externalAgentSessionId: ExternalAgentSessionId,
): AgentSessionState {
  const selectedTab = state.activeTabId;
  if (!selectedTab) {
    return state;
  }
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.tabId === selectedTab
        ? { ...session, externalAgentSessionId, lastUsedAt: Date.now() }
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
  return AGENT_CONFIG[agentId].webSocketUrl;
}

interface AgentConfig {
  port: number;
  command: string;
  webSocketUrl: string;
  sessionSupport: SessionSupportType;
}

const AGENT_CONFIG: Record<ExternalAgentId, AgentConfig> = {
  claude: {
    port: 3017,
    command: "npx @zed-industries/claude-code-acp",
    webSocketUrl: "ws://localhost:3017/message",
    sessionSupport: "single",
  },
  gemini: {
    port: 3019,
    command: "npx @google/gemini-cli --experimental-acp",
    webSocketUrl: "ws://localhost:3019/message",
    sessionSupport: "single",
  },
};

export function getAgentSessionSupport(
  agentId: ExternalAgentId,
): SessionSupportType {
  return AGENT_CONFIG[agentId].sessionSupport;
}

export function getAgentConnectionCommand(agentId: ExternalAgentId): string {
  const port = AGENT_CONFIG[agentId].port;
  const command = AGENT_CONFIG[agentId].command;
  return `npx stdio-to-ws "${command}" --port ${port}`;
}
