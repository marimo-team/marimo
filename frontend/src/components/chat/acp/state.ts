/* Copyright 2025 Marimo. All rights reserved. */

import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { capitalize } from "lodash-es";
import type { TypedString } from "@/utils/typed";
import { generateUUID } from "@/utils/uuid";
import type { SessionSupportType } from "./types";

// Types
export type TabId = TypedString<"TabId">;
export type ExternalAgentSessionId = TypedString<"ExternalAgentSessionId">;
export type ExternalAgentId = "claude" | "gemini";

export interface AgentSession {
  tabId: TabId;
  agentId: ExternalAgentId;
  title: string;
  createdAt: number;
  lastUsedAt: number;
  // Store the actual agent session ID for resumption
  externalAgentSessionId?: ExternalAgentSessionId;
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
  (get, set, activeTabId: TabId | null) => {
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

export function truncateTitle(title: string, maxLength: number = 20): string {
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
        ...session,
        title,
        createdAt: now,
        lastUsedAt: now,
        tabId: existingSession.tabId, // Keep the same ID to maintain tab reference
      };

      return {
        ...state,
        sessions: [...otherSessions, updatedSession],
        activeTabId: updatedSession.tabId,
      };
    }
  }

  // For multiple session agents or when no existing session exists
  return {
    ...state,
    sessions: [
      ...state.sessions,
      {
        ...session,
        tabId,
        title,
        createdAt: now,
        lastUsedAt: now,
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
  const newActiveSessionId =
    state.activeTabId === sessionId
      ? filteredSessions.length > 0
        ? filteredSessions[filteredSessions.length - 1].tabId
        : null
      : state.activeTabId;

  return {
    sessions: filteredSessions,
    activeTabId: newActiveSessionId,
  };
}

export function updateSessionTitle(
  state: AgentSessionState,
  sessionId: TabId,
  title: string,
): AgentSessionState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.tabId === sessionId
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

export function updateSessionExternalAgentSessionId(
  state: AgentSessionState,
  sessionId: TabId,
  externalAgentSessionId: ExternalAgentSessionId,
): AgentSessionState {
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.tabId === sessionId
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
  return `npx supergateway --stdio\\\n  "${command}" \\\n   --outputTransport ws --port ${port} `;
}
