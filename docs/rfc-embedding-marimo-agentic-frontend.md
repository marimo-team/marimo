# RFC: Frontend Implementation for Agentic Chat Experience

**Version:** 1.0
**Status:** Draft
**Authors:** Engineering Team
**Date:** January 2026

**Based on:** marimo's ACP (Agent Client Protocol) implementation
**Goal:** Replicate the agentic experience from marimo in your own product

---

## Executive Summary

This RFC documents how marimo implements its agentic chat experience on the frontend, providing a complete blueprint for replication. The implementation uses:

- **`use-acp`** (v0.2.6) - Zed Industries' Agent Client Protocol library
- **Jotai** for state management with localStorage persistence
- **React** with heavy memoization for performance
- **Radix UI** + **Tailwind CSS** for the component library
- **WebSocket** communication with JSON-RPC protocol

The architecture supports multiple agent types (Claude, Gemini, Codex, OpenCode), streaming responses, tool execution with permission approval, and session persistence.

---

## Table of Contents

1. [Core Dependencies](#1-core-dependencies)
2. [State Management Architecture](#2-state-management-architecture)
3. [Component Architecture](#3-component-architecture)
4. [ACP Client Integration](#4-acp-client-integration)
5. [Message Protocol & Types](#5-message-protocol--types)
6. [Message Rendering Pipeline](#6-message-rendering-pipeline)
7. [Permission/Approval Workflow](#7-permissionapproval-workflow)
8. [Session Management](#8-session-management)
9. [Backend Requirements](#9-backend-requirements)
10. [Styling Patterns](#10-styling-patterns)
11. [Implementation Checklist](#11-implementation-checklist)

---

## 1. Core Dependencies

### Required NPM Packages

```json
{
  "dependencies": {
    "use-acp": "0.2.6",
    "@zed-industries/agent-client-protocol": "^0.4.5",
    "jotai": "^2.16.1",
    "react-use-event-hook": "^0.9.6",
    "lucide-react": "^0.562.0",
    "@radix-ui/react-accordion": "~1.2.12",
    "@radix-ui/react-popover": "~1.1.15",
    "@radix-ui/react-select": "~2.2.6",
    "@radix-ui/react-tooltip": "~1.2.8",
    "lodash-es": "^4.17.22",
    "zod": "^4.3.4",
    "react-markdown": "^9.1.0",
    "tailwind-merge": "^2.6.0",
    "class-variance-authority": "^0.7.1"
  }
}
```

### Key Library: `use-acp`

The `use-acp` library provides the core ACP client functionality:

```typescript
import { useAcpClient, groupNotifications, mergeToolCalls, JsonRpcError } from "use-acp";
```

**Features:**
- WebSocket connection management with auto-reconnect
- JSON-RPC protocol handling
- Notification streaming and grouping
- Permission request/response handling
- Session lifecycle management

---

## 2. State Management Architecture

### Jotai Atoms for Session State

**File: `state.ts`**

```typescript
import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

// Types
export type TabId = TypedString<"TabId">;
export type ExternalAgentId = "claude" | "gemini" | "codex" | "opencode";
export type ExternalAgentSessionId = TypedString<"ExternalAgentSessionId">;
export type SessionSupportType = "single" | "multiple";

// Session interface
export interface AgentSession {
  tabId: TabId;                                    // Internal tab ID (UUID)
  agentId: ExternalAgentId;                        // Which agent
  title: string;                                   // Session title (truncated)
  createdAt: number;                               // Timestamp
  lastUsedAt: number;                              // Last access time
  externalAgentSessionId: ExternalAgentSessionId | null;  // Agent's session ID
  selectedModel: string | null;                    // Selected model
}

export interface AgentSessionState {
  sessions: AgentSession[];
  activeTabId: TabId | null;
}

// Storage key for localStorage persistence
const STORAGE_KEY = "marimo:acp:sessions:v1";

// Main session state atom with persistence
export const agentSessionStateAtom = atomWithStorage<AgentSessionState>(
  STORAGE_KEY,
  { sessions: [], activeTabId: null },
  // Custom JSON storage adapter
);

// Derived atom for currently selected tab
export const selectedTabAtom = atom(
  (get) => {
    const state = get(agentSessionStateAtom);
    if (!state.activeTabId) return null;
    return state.sessions.find((s) => s.tabId === state.activeTabId) || null;
  },
  (_get, set, activeTabId: TabId | null) => {
    set(agentSessionStateAtom, (prev) => ({
      ...prev,
      activeTabId,
    }));
  },
);
```

### Session State Utilities

```typescript
// Max sessions (marimo limits to 1 since agents don't support loading sessions)
const MAX_SESSIONS = 1;

export function addSession(
  state: AgentSessionState,
  session: { agentId: ExternalAgentId; firstMessage?: string; model?: string | null }
): AgentSessionState {
  const sessionSupport = getAgentSessionSupport(session.agentId);
  const now = Date.now();
  const title = session.firstMessage
    ? truncateTitle(session.firstMessage.trim())
    : `New ${session.agentId} session`;

  if (sessionSupport === "single") {
    // Replace existing session for this agent type
    const existingSessions = state.sessions.filter((s) => s.agentId === session.agentId);
    const otherSessions = state.sessions.filter((s) => s.agentId !== session.agentId);

    if (existingSessions.length > 0) {
      const existingSession = existingSessions[0];
      return {
        ...state,
        sessions: [...otherSessions, {
          ...existingSession,
          title,
          createdAt: now,
          lastUsedAt: now,
          externalAgentSessionId: null,  // Clear for new session
          selectedModel: session.model ?? existingSession.selectedModel,
        }],
        activeTabId: existingSession.tabId,
      };
    }
  }

  // Create new session
  const tabId = generateTabId();
  return {
    sessions: [...state.sessions.slice(0, MAX_SESSIONS - 1), {
      agentId: session.agentId,
      tabId,
      title,
      createdAt: now,
      lastUsedAt: now,
      externalAgentSessionId: null,
      selectedModel: session.model ?? null,
    }],
    activeTabId: tabId,
  };
}

export function removeSession(state: AgentSessionState, sessionId: TabId): AgentSessionState {
  const filtered = state.sessions.filter((s) => s.tabId !== sessionId);
  const newActive = state.activeTabId === sessionId
    ? (filtered.length > 0 ? filtered[filtered.length - 1].tabId : null)
    : state.activeTabId;
  return { sessions: filtered, activeTabId: newActive };
}

export function updateSessionExternalAgentSessionId(
  state: AgentSessionState,
  externalAgentSessionId: ExternalAgentSessionId
): AgentSessionState {
  const selectedTab = state.activeTabId;
  if (!selectedTab) return state;
  return {
    ...state,
    sessions: state.sessions.map((session) =>
      session.tabId === selectedTab
        ? { ...session, externalAgentSessionId, lastUsedAt: Date.now() }
        : session
    ),
  };
}
```

### Agent Configuration

```typescript
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
  codex: {
    port: 3021,
    command: "npx @zed-industries/codex-acp",
    webSocketUrl: "ws://localhost:3021/message",
    sessionSupport: "single",
  },
  opencode: {
    port: 3023,
    command: "npx opencode-ai acp",
    webSocketUrl: "ws://localhost:3023/message",
    sessionSupport: "single",
  },
};

export function getAgentWebSocketUrl(agentId: ExternalAgentId): string {
  return AGENT_CONFIG[agentId].webSocketUrl;
}

export function getAgentConnectionCommand(agentId: ExternalAgentId): string {
  const { port, command } = AGENT_CONFIG[agentId];
  return `npx stdio-to-ws "${command}" --port ${port}`;
}
```

---

## 3. Component Architecture

### Component Hierarchy

```
AgentPanel (main container)
├── AgentPanelHeader
│   ├── HeaderInfo (agent name + connection status badge)
│   ├── ConnectionControl (connect/disconnect button)
│   └── RestartButton (create new session)
├── SessionTabs
│   ├── SessionTab[] (tab for each session)
│   └── AgentSelector (dropdown to create new session)
├── ChatContent
│   ├── PermissionRequest (if pending approval)
│   ├── AgentThread (scrollable message container)
│   │   └── Notification Groups (grouped by type)
│   │       ├── ErrorBlock
│   │       ├── ConnectionChangeBlock
│   │       └── SessionNotificationsBlock
│   │           ├── AgentMessagesBlock (agent text responses)
│   │           ├── UserMessagesBlock (user inputs)
│   │           ├── AgentThoughtsBlock (thinking/reasoning)
│   │           ├── ToolNotificationsBlock (tool calls)
│   │           ├── PlansBlock (todo lists)
│   │           └── ContentBlocks (text, images, audio, resources)
│   └── ScrollToBottomButton
├── LoadingIndicator (spinner + stop button)
├── FileAttachmentPills (attached files)
└── PromptArea
    ├── PromptInput (CodeMirror-based text input)
    ├── ModeSelector (if agent supports modes)
    ├── ModelSelector (if agent supports models)
    ├── AddContextButton (@-mentions)
    ├── AttachFileButton
    └── SendButton / StopButton
```

### Main AgentPanel Component

**Key patterns:**

```typescript
const AgentPanel: React.FC = () => {
  // Local state
  const [isLoading, setIsLoading] = useState(false);
  const [promptValue, setPromptValue] = useState("");
  const [files, setFiles] = useState<File[]>();
  const [sessionModels, setSessionModels] = useState<SessionModelState | null>(null);

  // Jotai atoms
  const [selectedTab] = useAtom(selectedTabAtom);
  const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);

  // WebSocket URL based on selected agent
  const wsUrl = selectedTab
    ? getAgentWebSocketUrl(selectedTab.agentId)
    : "_skip_auto_connect_";

  // ACP Client hook
  const acpClient = useAcpClient({
    wsUrl,
    clientOptions: {
      readTextFile: (request) => sendFileDetails({ path: request.path })
        .then((response) => ({ content: response.contents || "" })),
      writeTextFile: (request) => sendUpdateFile({
        path: request.path,
        contents: request.content
      }).then(() => ({})),
    },
    autoConnect: false,  // Manual connection management
  });

  const {
    connect,
    disconnect,
    setActiveSessionId,
    connectionState,
    notifications,
    pendingPermission,
    resolvePermission,
    availableCommands,
    sessionMode,
    activeSessionId,
    agent,
    clearNotifications,
  } = acpClient;

  // Initialize protocol on agent ready
  useEffect(() => {
    agent?.initialize({
      protocolVersion: 1,
      clientCapabilities: {
        fs: { readTextFile: true, writeTextFile: true },
      },
    });
  }, [agent]);

  // ... rest of component
};
```

### Memoized Sub-components

All major components use `memo()` for performance:

```typescript
const AgentTitle = memo<{ currentAgentId?: ExternalAgentId }>(({ currentAgentId }) => (
  <span className="text-sm font-medium">{capitalize(currentAgentId)}</span>
));
AgentTitle.displayName = "AgentTitle";

const ConnectionControl = memo<ConnectionControlProps>(
  ({ connectionState, onConnect, onDisconnect }) => {
    const isConnected = connectionState.status === "connected";
    return (
      <Button
        variant="outline"
        size="xs"
        onClick={isConnected ? onDisconnect : onConnect}
        disabled={connectionState.status === "connecting"}
      >
        {isConnected ? "Disconnect" : "Connect"}
      </Button>
    );
  }
);
ConnectionControl.displayName = "ConnectionControl";
```

### Event Handler Pattern with `react-use-event-hook`

```typescript
import useEvent from "react-use-event-hook";

// Stable callback that always has latest state
const handlePromptSubmit = useEvent(async (_e: KeyboardEvent | undefined, prompt: string) => {
  if (!activeSessionId || !agent || isLoading) return;

  setIsLoading(true);
  setPromptValue("");
  setFiles(undefined);

  // Build prompt blocks
  const promptBlocks: ContentBlock[] = [{ type: "text", text: prompt }];

  // Add context and attachments
  const { contextBlocks, attachmentBlocks } = await parseContextFromPrompt(prompt);
  promptBlocks.push(...contextBlocks, ...attachmentBlocks);

  // Add file attachments
  if (files?.length) {
    const fileResourceLinks = await convertFilesToResourceLinks(files);
    promptBlocks.push(...fileResourceLinks);
  }

  try {
    await agent.prompt({
      sessionId: activeSessionId,
      prompt: promptBlocks,
    });
  } catch (error) {
    console.error("Failed to send prompt", { error });
  } finally {
    setIsLoading(false);
  }
});
```

---

## 4. ACP Client Integration

### Using `useAcpClient` Hook

```typescript
import { useAcpClient } from "use-acp";

const acpClient = useAcpClient({
  wsUrl: "ws://localhost:3017/message",

  clientOptions: {
    // File operations requested by agent
    readTextFile: async (request) => {
      const response = await yourApi.getFile(request.path);
      return { content: response.contents || "" };
    },
    writeTextFile: async (request) => {
      await yourApi.writeFile(request.path, request.content);
      return {};
    },
  },

  autoConnect: false,  // Control connection manually
});
```

### ACP Client Return Values

```typescript
const {
  // Connection management
  connect,              // () => Promise<void> - Connect to WebSocket
  disconnect,           // () => void - Disconnect
  connectionState,      // { status: "connected" | "connecting" | "disconnected" | "error" }

  // Session management
  activeSessionId,      // string | null - Current session ID
  setActiveSessionId,   // (id: string | null) => void

  // Notifications
  notifications,        // NotificationEvent[] - All events from agent
  clearNotifications,   // (sessionId: string) => void

  // Permissions
  pendingPermission,    // AgentPendingPermission | null - Current permission request
  resolvePermission,    // (response: RequestPermissionResponse) => void

  // Agent capabilities
  availableCommands,    // Command[] - Slash commands
  sessionMode,          // SessionMode - Available/current modes

  // Agent client instance
  agent,                // Agent client with methods:
                        //   - initialize(options)
                        //   - newSession(options)
                        //   - loadSession(options)
                        //   - prompt(options)
                        //   - cancel(options)
                        //   - setSessionModel(options)
                        //   - setSessionMode(options)
} = acpClient;
```

### Session Lifecycle

```typescript
// 1. Create new session
const handleNewSession = useEvent(async () => {
  if (!agent) return;

  // Cancel existing session if any
  if (activeSessionId) {
    await agent.cancel({ sessionId: activeSessionId }).catch(console.error);
    clearNotifications(activeSessionId);
    setActiveSessionId(null);
  }

  // Create new session
  const newSession = await agent.newSession({
    cwd: getCwd(),           // Working directory
    mcpServers: [],          // MCP servers to connect
    _meta: selectedModel ? { model: selectedModel } : undefined,
  });

  // Capture available models
  if (newSession.models) {
    setSessionModels(newSession.models);
  }

  // Store session ID
  setSessionState((prev) => updateSessionExternalAgentSessionId(
    prev,
    newSession.sessionId as ExternalAgentSessionId
  ));
});

// 2. Resume existing session
const handleResumeSession = useEvent(async (previousSessionId: ExternalAgentSessionId) => {
  if (!agent?.loadSession) {
    throw new Error("Agent does not support loading sessions");
  }

  const loadedSession = await agent.loadSession({
    sessionId: previousSessionId,
    cwd: getCwd(),
    mcpServers: [],
  });

  if (loadedSession?.models) {
    setSessionModels(loadedSession.models);
  }

  setSessionState((prev) => updateSessionExternalAgentSessionId(prev, previousSessionId));
});

// 3. Auto-create/resume on connect
useEffect(() => {
  if (!isConnected || !selectedTab || !agent) return;
  if (activeSessionId && tabLastActiveSessionId) return;  // Already have session

  const createOrResumeSession = async () => {
    const availableSession = tabLastActiveSessionId ?? activeSessionId;
    if (availableSession) {
      try {
        await handleResumeSession(availableSession);
      } catch {
        await handleNewSession();  // Fallback to new session
      }
    } else {
      await handleNewSession();
    }
  };

  createOrResumeSession();
}, [isConnected, agent, tabLastActiveSessionId, activeSessionId]);
```

---

## 5. Message Protocol & Types

### Notification Event Types

**File: `types.ts`**

```typescript
import type {
  ContentBlock,
  ToolCall,
  PermissionOption,
} from "@zed-industries/agent-client-protocol";

// Connection state
export type AgentConnectionState = {
  status: "connected" | "connecting" | "disconnected" | "error";
};

// Notification event (from use-acp)
export type NotificationEvent =
  | ErrorNotificationEvent
  | ConnectionChangeNotificationEvent
  | SessionNotificationEvent;

// Error notification
export interface ErrorNotificationEvent {
  type: "error";
  data: {
    message: string;
    code?: number;
    data?: unknown;
  };
  timestamp: number;
}

// Connection change
export interface ConnectionChangeNotificationEvent {
  type: "connection_change";
  data: {
    status: "connected" | "connecting" | "disconnected" | "error";
  };
  timestamp: number;
}

// Session notification (the main message type)
export interface SessionNotificationEvent {
  type: "session_notification";
  data: {
    sessionId: string;
    update: SessionNotificationEventData;
  };
  timestamp: number;
}

// Session update types
export type SessionNotificationEventData =
  | UserNotificationEvent
  | AgentNotificationEvent
  | AgentThoughtNotificationEvent
  | ToolCallNotificationEvent
  | ToolCallUpdateNotificationEvent
  | PlanNotificationEvent
  | CurrentModeUpdateNotificationEvent
  | AvailableCommandsUpdateNotificationEvent;

// User message chunk
export interface UserNotificationEvent {
  sessionUpdate: "user_message_chunk";
  content: ContentBlock;
}

// Agent message chunk (streaming)
export interface AgentNotificationEvent {
  sessionUpdate: "agent_message_chunk";
  content: ContentBlock;
}

// Agent thought/reasoning
export interface AgentThoughtNotificationEvent {
  sessionUpdate: "agent_thought_chunk";
  content: ContentBlock;
}

// Tool call initiated
export interface ToolCallNotificationEvent {
  sessionUpdate: "tool_call";
  toolCallId: string;
  kind: string;
  title?: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  locations?: ToolCallLocation[];
  content?: ToolCallContent[];
  rawInput?: Record<string, unknown>;
}

// Tool call update (progress/completion)
export interface ToolCallUpdateNotificationEvent {
  sessionUpdate: "tool_call_update";
  toolCallId: string;
  kind: string;
  title?: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  locations?: ToolCallLocation[];
  content?: ToolCallContent[];
  rawInput?: Record<string, unknown>;
}

// Plan/todo list
export interface PlanNotificationEvent {
  sessionUpdate: "plan";
  entries: Array<{
    content: string;
    status: "pending" | "in_progress" | "completed";
  }>;
}

// Permission request
export interface AgentPendingPermission {
  toolCall: ToolCall;
  options: PermissionOption[];
}

// Content block types
export type ContentBlockOf<T extends ContentBlock["type"]> =
  Extract<ContentBlock, { type: T }>;
```

### Type Guards for Notification Filtering

```typescript
// utils.ts
export function isUserMessages(
  items: SessionNotificationEventData[]
): items is UserNotificationEvent[] {
  return items[0]?.sessionUpdate === "user_message_chunk";
}

export function isAgentMessages(
  items: SessionNotificationEventData[]
): items is AgentNotificationEvent[] {
  return items[0]?.sessionUpdate === "agent_message_chunk";
}

export function isAgentThoughts(
  items: SessionNotificationEventData[]
): items is AgentThoughtNotificationEvent[] {
  return items[0]?.sessionUpdate === "agent_thought_chunk";
}

export function isToolCalls(
  items: SessionNotificationEventData[]
): items is (ToolCallNotificationEvent | ToolCallUpdateNotificationEvent)[] {
  return (
    items[0]?.sessionUpdate === "tool_call" ||
    items[0]?.sessionUpdate === "tool_call_update"
  );
}

export function isPlans(
  items: SessionNotificationEventData[]
): items is PlanNotificationEvent[] {
  return items[0]?.sessionUpdate === "plan";
}
```

---

## 6. Message Rendering Pipeline

### Notification Grouping

The `use-acp` library provides `groupNotifications()` to coalesce related events:

```typescript
import { groupNotifications } from "use-acp";

// In AgentThread component
const AgentThread: React.FC<{ notifications: NotificationEvent[] }> = ({
  notifications,
}) => {
  // Filter out redundant notifications
  const filtered = notifications.filter((n) => {
    // Skip connection changes in middle of conversation
    if (n.type === "connection_change" && /* other conditions */) return false;
    // Skip command updates (no visual representation)
    if (n.type === "session_notification" &&
        n.data.update.sessionUpdate === "available_commands_update") return false;
    return true;
  });

  // Group consecutive notifications of same type
  const grouped = groupNotifications(filtered);

  return (
    <div className="flex flex-col gap-2 p-2">
      {grouped.map((group, index) => (
        <NotificationGroup
          key={index}
          group={group}
          isLastBlock={index === grouped.length - 1}
        />
      ))}
    </div>
  );
};
```

### Merging Consecutive Text Blocks

Streaming responses come as multiple text chunks. Merge them to prevent fragmented display:

```typescript
function mergeConsecutiveTextBlocks(contentBlocks: ContentBlock[]): ContentBlock[] {
  if (contentBlocks.length === 0) return contentBlocks;

  const merged: ContentBlock[] = [];
  let currentText: string | null = null;

  for (const block of contentBlocks) {
    if (block.type === "text") {
      currentText = currentText === null ? block.text : currentText + block.text;
    } else {
      // Flush accumulated text before non-text block
      if (currentText !== null) {
        merged.push({ type: "text", text: currentText });
        currentText = null;
      }
      merged.push(block);
    }
  }

  // Flush remaining text
  if (currentText !== null) {
    merged.push({ type: "text", text: currentText });
  }

  return merged;
}
```

### Content Block Rendering

```typescript
const ContentBlocks: React.FC<{ data: ContentBlock[] }> = ({ data }) => {
  const renderBlock = (block: ContentBlock) => {
    switch (block.type) {
      case "text":
        return <MarkdownRenderer content={block.text} />;
      case "image":
        return (
          <img
            src={`data:${block.mimeType};base64,${block.data}`}
            alt={block.uri ?? ""}
          />
        );
      case "audio":
        return (
          <audio
            src={`data:${block.mimeType};base64,${block.data}`}
            controls
          />
        );
      case "resource":
        return <ResourceBlock data={block} />;
      case "resource_link":
        return <ResourceLinkBlock data={block} />;
      default:
        return null;
    }
  };

  return (
    <div>
      {data.map((block, index) => (
        <React.Fragment key={`${block.type}-${index}`}>
          {renderBlock(block)}
        </React.Fragment>
      ))}
    </div>
  );
};
```

### Tool Call Rendering

```typescript
import { mergeToolCalls } from "use-acp";

const ToolNotificationsBlock: React.FC<{
  data: (ToolCallNotificationEvent | ToolCallUpdateNotificationEvent)[];
  isLastBlock: boolean;
}> = ({ data, isLastBlock }) => {
  // Merge tool call events with their updates
  const toolCalls = mergeToolCalls(data);

  return (
    <div className="flex flex-col">
      {toolCalls.map((item) => (
        <SimpleAccordion
          key={item.toolCallId}
          status={
            item.status === "completed" ? "success" :
            item.status === "failed" ? "error" :
            (item.status === "in_progress" || item.status === "pending") && !isLastBlock
              ? "loading" : undefined
          }
          title={toolTitle(item)}
          defaultIcon={<WrenchIcon className="h-3 w-3" />}
        >
          <ToolBodyBlock data={item} />
        </SimpleAccordion>
      ))}
    </div>
  );
};

// Show diff blocks for file edits
const DiffBlocks: React.FC<{ data: DiffContent[] }> = ({ data }) => (
  <div className="flex flex-col gap-2">
    {data.map((item) => (
      <div key={item.path} className="border rounded-md overflow-hidden">
        <div className="px-2 py-1 bg-muted border-b text-xs font-medium">
          {item.path}
        </div>
        <ReadonlyDiff original={item.oldText || ""} modified={item.newText || ""} />
      </div>
    ))}
  </div>
);
```

---

## 7. Permission/Approval Workflow

### Permission Request Component

```typescript
interface PermissionRequestProps {
  permission: AgentPendingPermission;
  onResolve: (option: RequestPermissionResponse) => void;
}

const PermissionRequest: React.FC<PermissionRequestProps> = memo(
  ({ permission, onResolve }) => (
    <div className="border border-amber-500 bg-amber-50 dark:bg-amber-950 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-3">
        <ShieldCheckIcon className="h-4 w-4 text-amber-600" />
        <h3 className="text-sm font-medium text-amber-800 dark:text-amber-200">
          Permission Request
        </h3>
      </div>

      <p className="text-sm text-amber-700 dark:text-amber-300 mb-3">
        The AI agent is requesting permission to proceed:
      </p>

      {/* Show what the tool wants to do */}
      <ToolBodyBlock data={permission.toolCall} />

      {/* Permission options (allow/reject) */}
      <div className="flex gap-2 mt-3">
        {permission.options.map((option) => (
          <Button
            key={option.optionId}
            size="sm"
            variant={option.kind.startsWith("allow") ? "default" : "destructive"}
            onClick={() => onResolve({
              outcome: {
                outcome: "selected",
                optionId: option.optionId,
              },
            })}
          >
            {option.kind.startsWith("allow") && <CheckCircleIcon className="h-3 w-3 mr-1" />}
            {option.kind.startsWith("reject") && <XCircleIcon className="h-3 w-3 mr-1" />}
            {option.name}
          </Button>
        ))}
      </div>
    </div>
  )
);
```

### Permission Options

Common permission option kinds from agents:

```typescript
type PermissionKind =
  | "allow_once"      // Allow this one action
  | "allow_all"       // Allow all similar actions
  | "reject"          // Reject this action
  | "reject_all";     // Reject all similar actions
```

### Integrating Permission UI

```typescript
const ChatContent: React.FC<ChatContentProps> = ({
  pendingPermission,
  onResolvePermission,
  // ...other props
}) => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Permission request at top of chat */}
      {pendingPermission && (
        <div className="p-3 border-b">
          <PermissionRequest
            permission={pendingPermission}
            onResolve={onResolvePermission}
          />
        </div>
      )}

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto">
        <AgentThread notifications={notifications} />
      </div>
    </div>
  );
};

// In parent component
<ChatContent
  pendingPermission={pendingPermission}
  onResolvePermission={(option) => {
    resolvePermission(option);  // From useAcpClient
  }}
/>
```

---

## 8. Session Management

### Multi-Agent Session Tabs

```typescript
const SessionTabs: React.FC = () => {
  const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);
  const [selectedTab, setSelectedTab] = useAtom(selectedTabAtom);

  return (
    <div className="flex items-center gap-1 px-2 py-1 border-b bg-muted/30">
      {sessionState.sessions.map((session) => (
        <SessionTab
          key={session.tabId}
          session={session}
          isActive={session.tabId === selectedTab?.tabId}
          onSelect={() => setSelectedTab(session.tabId)}
          onClose={() => setSessionState((prev) => removeSession(prev, session.tabId))}
        />
      ))}

      {sessionState.sessions.length < MAX_SESSIONS && (
        <AgentSelector className="border rounded" />
      )}
    </div>
  );
};

const SessionTab: React.FC<{
  session: AgentSession;
  isActive: boolean;
  onSelect: () => void;
  onClose: () => void;
}> = memo(({ session, isActive, onSelect, onClose }) => (
  <div
    className={cn(
      "flex items-center gap-2 px-3 py-1 rounded cursor-pointer",
      isActive ? "bg-background border" : "hover:bg-muted/50"
    )}
    onClick={onSelect}
  >
    <BotMessageSquareIcon className="h-3 w-3" />
    <span className="text-xs truncate max-w-[100px]">{session.title}</span>
    <button
      onClick={(e) => { e.stopPropagation(); onClose(); }}
      className="hover:bg-muted rounded p-0.5"
    >
      <XIcon className="h-3 w-3" />
    </button>
  </div>
));
```

### Agent Selector Dropdown

```typescript
const AgentSelector: React.FC<{ className?: string }> = ({ className }) => {
  const [, setSessionState] = useAtom(agentSessionStateAtom);

  const handleSelectAgent = (agentId: ExternalAgentId) => {
    setSessionState((prev) => addSession(prev, { agentId }));
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className={className}>
          <PlusIcon className="h-3 w-3 mr-1" />
          New Session
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        {getAllAgentIds().map((agentId) => (
          <DropdownMenuItem
            key={agentId}
            onClick={() => handleSelectAgent(agentId)}
          >
            {getAgentDisplayName(agentId)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
```

---

## 9. Backend Requirements

### For Custom Agents (Your Own Backend)

If building your own agent backend instead of using Claude/Gemini directly:

#### WebSocket Server

```python
# FastAPI example
from fastapi import FastAPI, WebSocket
import json

app = FastAPI()

@app.websocket("/message")
async def agent_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle JSON-RPC methods
            if message.get("method") == "initialize":
                await handle_initialize(websocket, message)
            elif message.get("method") == "session/new":
                await handle_new_session(websocket, message)
            elif message.get("method") == "session/prompt":
                await handle_prompt(websocket, message)
            # ... more methods

    except WebSocketDisconnect:
        pass
```

#### JSON-RPC Methods to Implement

```python
# Required methods
async def handle_initialize(ws, message):
    """Protocol initialization"""
    await ws.send_text(json.dumps({
        "jsonrpc": "2.0",
        "id": message["id"],
        "result": {
            "protocolVersion": 1,
            "serverCapabilities": {
                "models": [{"id": "your-model", "name": "Your Model"}],
                "modes": [],
            }
        }
    }))

async def handle_new_session(ws, message):
    """Create new chat session"""
    session_id = generate_session_id()
    # ... create session
    await ws.send_text(json.dumps({
        "jsonrpc": "2.0",
        "id": message["id"],
        "result": {
            "sessionId": session_id,
            "models": {...}
        }
    }))

async def handle_prompt(ws, message):
    """Handle user message, stream response"""
    session_id = message["params"]["sessionId"]
    prompt = message["params"]["prompt"]

    # Stream agent response chunks
    async for chunk in your_llm_stream(prompt):
        await ws.send_text(json.dumps({
            "jsonrpc": "2.0",
            "method": "session/notification",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": chunk}
                }
            }
        }))
```

#### File Operations Backend

If your agent needs file read/write capabilities:

```python
# The frontend will call these via clientOptions
@app.post("/api/files/read")
async def read_file(path: str):
    """Read file contents for agent context"""
    with open(path) as f:
        return {"contents": f.read()}

@app.post("/api/files/write")
async def write_file(path: str, contents: str):
    """Write file from agent edit"""
    with open(path, "w") as f:
        f.write(contents)
    return {"success": True}
```

### For Using Existing Agents (stdio-to-ws)

Use `stdio-to-ws` to bridge existing CLI agents:

```bash
# Start Claude agent
npx stdio-to-ws "npx @zed-industries/claude-code-acp" --port 3017

# Start Gemini agent
npx stdio-to-ws "npx @google/gemini-cli --experimental-acp" --port 3019
```

The frontend connects to these WebSocket endpoints directly.

---

## 10. Styling Patterns

### Color System (Radix UI Colors)

```css
/* Use CSS variables from Radix colors */
.error-block {
  background: var(--red-2);
  border-color: var(--red-6);
  color: var(--red-11);
}

.warning-block {
  background: var(--amber-2);
  border-color: var(--amber-6);
  color: var(--amber-11);
}

.success-block {
  background: var(--blue-2);
  border-color: var(--blue-6);
  color: var(--blue-11);
}

.muted {
  background: var(--gray-2);
  color: var(--gray-11);
}
```

### Component Variants with CVA

```typescript
import { cva } from "class-variance-authority";

const statusBadge = cva(
  "flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium",
  {
    variants: {
      status: {
        connected: "bg-blue-100 text-blue-800 border-blue-200",
        connecting: "bg-yellow-100 text-yellow-800 border-yellow-200",
        disconnected: "bg-red-100 text-red-800 border-red-200",
      },
    },
    defaultVariants: {
      status: "disconnected",
    },
  }
);
```

### Dark Mode Support

All components should work in both light and dark modes using Tailwind's dark: prefix or CSS variables:

```tsx
<div className="bg-background text-foreground dark:bg-gray-900 dark:text-gray-100">
  <div className="border-border dark:border-gray-700">
    {/* Content */}
  </div>
</div>
```

---

## 11. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Install dependencies (`use-acp`, `jotai`, UI libraries)
- [ ] Set up Jotai provider and atoms
- [ ] Create TypeScript types for all notification events
- [ ] Implement type guards for notification filtering

### Phase 2: State Management
- [ ] Implement `agentSessionStateAtom` with localStorage persistence
- [ ] Implement `selectedTabAtom` derived atom
- [ ] Implement session utility functions (add, remove, update)
- [ ] Configure agent endpoints (ports, WebSocket URLs)

### Phase 3: ACP Client Integration
- [ ] Set up `useAcpClient` hook with file operations
- [ ] Implement connection lifecycle (connect, disconnect, reconnect)
- [ ] Implement session lifecycle (create, resume, cancel)
- [ ] Wire up protocol initialization

### Phase 4: Component Architecture
- [ ] Create `AgentPanel` main container
- [ ] Create `AgentPanelHeader` with connection controls
- [ ] Create `SessionTabs` for multi-session support
- [ ] Create `AgentSelector` dropdown
- [ ] Create `ChatContent` scrollable container
- [ ] Create `PromptArea` with input and buttons
- [ ] Create `LoadingIndicator` with stop button

### Phase 5: Message Rendering
- [ ] Create `AgentThread` for notification grouping
- [ ] Create `ContentBlocks` for rendering all content types
- [ ] Create `AgentMessagesBlock` with text merging
- [ ] Create `UserMessagesBlock`
- [ ] Create `ToolNotificationsBlock` with accordion
- [ ] Create `DiffBlocks` for file changes
- [ ] Create `PlansBlock` for todo lists
- [ ] Create `AgentThoughtsBlock` for reasoning

### Phase 6: Permission System
- [ ] Create `PermissionRequest` component
- [ ] Wire up `resolvePermission` callback
- [ ] Display permission request in chat UI
- [ ] Show loading state while awaiting permission

### Phase 7: Polish
- [ ] Add auto-scroll to bottom
- [ ] Add scroll-to-bottom button
- [ ] Add file attachment support
- [ ] Add @ context completion
- [ ] Add model selector
- [ ] Add mode selector
- [ ] Optimize with memo() where needed

### Phase 8: Testing
- [ ] Test connection lifecycle
- [ ] Test session create/resume/cancel
- [ ] Test message streaming
- [ ] Test permission workflow
- [ ] Test file attachments
- [ ] Test multi-agent switching

---

## Summary

This RFC provides a complete blueprint for implementing marimo's agentic chat experience. The key components are:

1. **`use-acp` library** - Handles WebSocket protocol, streaming, and permissions
2. **Jotai atoms** - Manage session state with persistence
3. **Memoized components** - Performant UI with React best practices
4. **Notification grouping** - Clean message display from streamed events
5. **Permission workflow** - User approval for sensitive operations

The architecture supports multiple agent types, streaming responses, tool execution visibility, and a polished user experience that matches or exceeds the original marimo implementation.
