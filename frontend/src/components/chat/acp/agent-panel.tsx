/* Copyright 2025 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { capitalize } from "lodash-es";
import { BotMessageSquareIcon, StopCircleIcon } from "lucide-react";
import React, { memo, useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { useAcpClient } from "use-acp";
import {
  ConnectionStatus,
  PermissionRequest,
} from "@/components/chat/acp/common";
import { PromptInput } from "@/components/editor/ai/add-cell-with-ai";
import { PanelEmptyState } from "@/components/editor/chrome/panels/empty-state";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { AgentSelector } from "./agent-selector";
import ScrollToBottomButton from "./scroll-to-bottom-button";
import { SessionTabs } from "./session-tabs";
import {
  activeSessionAtom,
  agentSessionStateAtom,
  type ExternalAgentId,
  getAgentWebSocketUrl,
  updateSessionAgentId,
  updateSessionTitle,
} from "./state";
import { AgentThread } from "./thread";
import "./agent-panel.css";

interface AgentTitleProps {
  currentAgentId?: ExternalAgentId;
}

const AgentTitle = memo<AgentTitleProps>(({ currentAgentId }) => (
  <span className="text-sm font-medium">
    {currentAgentId ? `${capitalize(currentAgentId)}` : "Agents"}
  </span>
));
AgentTitle.displayName = "AgentTitle";

interface ConnectionControlProps {
  connectionState: ReturnType<typeof useAcpClient>["connectionState"];
  onConnect: () => void;
  onDisconnect: () => void;
}

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
  },
);
ConnectionControl.displayName = "ConnectionControl";

interface HeaderInfoProps {
  currentAgentId?: ExternalAgentId;
  connectionStatus: string;
}

const HeaderInfo = memo<HeaderInfoProps>(
  ({ currentAgentId, connectionStatus }) => (
    <div className="flex items-center gap-2">
      <BotMessageSquareIcon className="h-4 w-4 text-muted-foreground" />
      <AgentTitle currentAgentId={currentAgentId} />
      <ConnectionStatus status={connectionStatus} />
    </div>
  ),
);
HeaderInfo.displayName = "HeaderInfo";

interface AgentPanelHeaderProps {
  connectionState: ReturnType<typeof useAcpClient>["connectionState"];
  currentAgentId?: ExternalAgentId;
  onConnect: () => void;
  onDisconnect: () => void;
}

const AgentPanelHeader = memo<AgentPanelHeaderProps>(
  ({ connectionState, currentAgentId, onConnect, onDisconnect }) => (
    <div className="flex border-b px-3 py-2 justify-between shrink-0 items-center">
      <HeaderInfo
        currentAgentId={currentAgentId}
        connectionStatus={connectionState.status}
      />
      <ConnectionControl
        connectionState={connectionState}
        onConnect={onConnect}
        onDisconnect={onDisconnect}
      />
    </div>
  ),
);
AgentPanelHeader.displayName = "AgentPanelHeader";

interface EmptyStateProps {
  currentAgentId?: ExternalAgentId;
  connectionState: ReturnType<typeof useAcpClient>["connectionState"];
  onConnect: () => void;
  onDisconnect: () => void;
}

const EmptyState = memo<EmptyStateProps>(
  ({ currentAgentId, connectionState, onConnect, onDisconnect }) => (
    <div className="flex flex-col h-full">
      <AgentPanelHeader
        connectionState={connectionState}
        currentAgentId={currentAgentId}
        onConnect={onConnect}
        onDisconnect={onDisconnect}
      />
      <SessionTabs />
      <div className="flex-1 flex items-center justify-center">
        <PanelEmptyState
          title="No Agent Sessions"
          description="Create a new session to start a conversation"
          action={<AgentSelector className="border-y-1 rounded" />}
          icon={<BotMessageSquareIcon />}
        />
      </div>
    </div>
  ),
);
EmptyState.displayName = "EmptyState";

interface LoadingIndicatorProps {
  isLoading: boolean;
  isRequestingPermission: boolean;
  onStop: () => void;
}

const LoadingIndicator = memo<LoadingIndicatorProps>(
  ({ isLoading, isRequestingPermission, onStop }) => {
    if (!isLoading) return null;

    return (
      <div className="px-3 py-2 border-t bg-muted/30 flex-shrink-0">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <Spinner size="small" className="text-primary" />
            {isRequestingPermission ? (
              <span>Waiting for permission to continue...</span>
            ) : (
              <span>Agent is working...</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={onStop}
              className="h-6 px-2"
            >
              <StopCircleIcon className="h-3 w-3 mr-1" />
              <span className="text-xs">Stop</span>
            </Button>
          </div>
        </div>
      </div>
    );
  },
);
LoadingIndicator.displayName = "LoadingIndicator";

interface PromptAreaProps {
  isLoading: boolean;
  currentSession: string | null;
  promptValue: string;
  onPromptValueChange: (value: string) => void;
  onPromptSubmit: (e: KeyboardEvent | undefined, prompt: string) => void;
}

const PromptArea = memo<PromptAreaProps>(
  ({
    isLoading,
    currentSession,
    promptValue,
    onPromptValueChange,
    onPromptSubmit,
  }) => (
    <div
      className={cn(
        "px-3 py-2 border-t bg-background flex-shrink-0 min-h-[80px]",
        (isLoading || !currentSession) && "opacity-50 pointer-events-none",
      )}
    >
      <PromptInput
        value={promptValue}
        onChange={isLoading ? () => {} : onPromptValueChange}
        onSubmit={onPromptSubmit}
        onClose={() => {}}
        placeholder={isLoading ? "Processing..." : "Ask your AI agent..."}
        className={isLoading ? "opacity-50 pointer-events-none" : ""}
        maxHeight="120px"
      />
    </div>
  ),
);
PromptArea.displayName = "PromptArea";

interface ChatContentProps {
  hasNotifications: boolean;
  connectionState: ReturnType<typeof useAcpClient>["connectionState"];
  notifications: any[];
  pendingPermission: any;
  onResolvePermission: (option: any) => void;
  onRetryConnection?: () => void;
  onRetryLastAction?: () => void;
  onDismissError?: (errorId: string) => void;
}

const ChatContent = memo<ChatContentProps>(
  ({
    hasNotifications,
    connectionState,
    notifications,
    pendingPermission,
    onResolvePermission,
    onRetryConnection,
    onRetryLastAction,
    onDismissError,
  }) => {
    const [isScrolledToBottom, setIsScrolledToBottom] = useState(true);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    const handleScroll = useEvent(() => {
      const container = scrollContainerRef.current;
      if (!container) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const isAtBottom = Math.abs(scrollHeight - clientHeight - scrollTop) < 5; // 5px threshold
      setIsScrolledToBottom(isAtBottom);
    });

    const scrollToBottom = useEvent(() => {
      const container = scrollContainerRef.current;
      if (!container) return;

      container.scrollTo({
        top: container.scrollHeight,
        behavior: "smooth",
      });
    });

    // Auto-scroll to bottom when new notifications arrive (if already at bottom)
    useEffect(() => {
      if (isScrolledToBottom && notifications.length > 0) {
        // Use setTimeout to ensure DOM is updated before scrolling
        setTimeout(scrollToBottom, 100);
      }
    }, [notifications.length, isScrolledToBottom, scrollToBottom]);

    return (
      <div className="flex-1 flex flex-col overflow-hidden flex-shrink-0 relative">
        {pendingPermission && (
          <div className="p-1 border-b">
            <PermissionRequest
              permission={pendingPermission}
              onResolve={onResolvePermission}
            />
          </div>
        )}

        <div
          ref={scrollContainerRef}
          className="flex-1 bg-muted/20 w-full flex flex-col overflow-y-auto"
          onScroll={handleScroll}
        >
          <div className="p-3">
            {hasNotifications ? (
              <div className="space-y-2">
                <AgentThread
                  isConnected={connectionState.status === "connected"}
                  notifications={notifications}
                  onRetryConnection={onRetryConnection}
                  onRetryLastAction={onRetryLastAction}
                  onDismissError={onDismissError}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full min-h-[200px]">
                <PanelEmptyState
                  title="Waiting for agent"
                  description="Your AI agent will appear here when active"
                  icon={<BotMessageSquareIcon />}
                />
              </div>
            )}
          </div>
        </div>

        <ScrollToBottomButton
          isVisible={!isScrolledToBottom && hasNotifications}
          onScrollToBottom={scrollToBottom}
        />
      </div>
    );
  },
);
ChatContent.displayName = "ChatContent";

const AgentPanel: React.FC = () => {
  const [currentSession, setCurrentSession] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [promptValue, setPromptValue] = useState("");
  const [hasAttemptedConnection, setHasAttemptedConnection] = useState(false);
  const [connectionAttemptedForSession, setConnectionAttemptedForSession] =
    useState<string | null>(null);

  const [activeSession] = useAtom(activeSessionAtom);
  const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);

  const wsUrl = activeSession
    ? getAgentWebSocketUrl(activeSession.agentId)
    : "ws://localhost:8000/message";

  const acpClient = useAcpClient({
    wsUrl,
    autoConnect: false, // We'll manage connection manually based on active session
  });

  const {
    connect,
    disconnect,
    connectionState,
    notifications,
    pendingPermission,
    resolvePermission,
    agent,
  } = acpClient;

  // Auto-connect when we have an active session, but only once per session
  useEffect(() => {
    if (
      activeSession &&
      connectionState.status === "disconnected" &&
      !hasAttemptedConnection &&
      connectionAttemptedForSession !== activeSession.id
    ) {
      setHasAttemptedConnection(true);
      setConnectionAttemptedForSession(activeSession.id);
      connect();
    }
  }, [
    activeSession,
    connectionState.status,
    connect,
    hasAttemptedConnection,
    connectionAttemptedForSession,
  ]);

  // Reset connection attempt tracking when active session changes
  useEffect(() => {
    if (activeSession && connectionAttemptedForSession !== activeSession.id) {
      setHasAttemptedConnection(false);
    }
  }, [activeSession, connectionAttemptedForSession]);

  // Reset connection attempt tracking on successful connection
  useEffect(() => {
    if (connectionState.status === "connected") {
      setHasAttemptedConnection(false);
    }
  }, [connectionState.status]);

  // Create or resume a session when successfully connected
  useEffect(() => {
    if (
      connectionState.status === "connected" &&
      agent &&
      activeSession &&
      !currentSession
    ) {
      const createOrResumeSession = async () => {
        try {
          let sessionId: string;
          const newSessionRequest = {
            cwd: "",
            mcpServers: [],
          };

          // Try to resume existing session if we have an agentSessionId
          if (activeSession.agentSessionId) {
            try {
              Logger.log(
                `[external-agents] Attempting to resume session: ${activeSession.agentSessionId}`,
              );
              const resumedSession = await agent.loadSession?.({
                sessionId: activeSession.agentSessionId,
                ...newSessionRequest,
              });

              sessionId = activeSession.agentSessionId;
              Logger.log(
                `[external-agents] Successfully resumed session: ${sessionId}, ${resumedSession}`,
              );
            } catch (resumeError) {
              Logger.log(
                "[external-agents] Failed to resume session, creating new session:",
                resumeError,
              );
              // Fall back to creating new session
              const newSession = await agent.newSession(newSessionRequest);
              sessionId = newSession.sessionId;

              // Update our state with the new agent session ID
              setSessionState((prev) =>
                updateSessionAgentId(prev, activeSession.id, sessionId),
              );
            }
          } else {
            // Create new session
            Logger.log("[external-agents] Creating new session");
            const newSession = await agent.newSession(newSessionRequest);
            sessionId = newSession.sessionId;

            // Update our state with the new agent session ID
            setSessionState((prev) =>
              updateSessionAgentId(prev, activeSession.id, sessionId),
            );
          }

          setCurrentSession(sessionId);
        } catch (error) {
          Logger.error("Failed to create or resume session:", error);
        }
      };

      createOrResumeSession();
    }
    // Reset session when disconnected
    if (connectionState.status === "disconnected") {
      setCurrentSession(null);
    }
  }, [
    connectionState.status,
    agent,
    activeSession,
    currentSession,
    setSessionState,
  ]);

  // Handler for prompt submission
  const handlePromptSubmit = useEvent(
    async (_e: KeyboardEvent | undefined, prompt: string) => {
      if (!currentSession || !agent || isLoading || !activeSession) return;

      setIsLoading(true);
      setPromptValue("");

      // Update session title with first message if it's still the default
      if (activeSession.title.startsWith("New ")) {
        setSessionState((prev) =>
          updateSessionTitle(prev, activeSession.id, prompt),
        );
      }

      try {
        await agent.prompt({
          sessionId: currentSession,
          prompt: [{ type: "text", text: prompt }],
        });
      } catch (error) {
        console.error("Failed to send prompt:", error);
      } finally {
        setIsLoading(false);
      }
    },
  );

  // Handler for stopping the current operation
  const handleStop = useEvent(() => {
    if (!currentSession) return;
    agent?.cancel({ sessionId: currentSession });
    setIsLoading(false);
  });

  // Handler for manual connect - allows retry after failed auto-connect
  const handleManualConnect = useEvent(() => {
    setHasAttemptedConnection(false);
    if (activeSession) {
      setConnectionAttemptedForSession(activeSession.id);
    }
    connect();
  });

  // Handler for manual disconnect
  const handleManualDisconnect = useEvent(() => {
    disconnect();
  });

  // Handler for retry connection from error/connection components
  const handleRetryConnection = useEvent(() => {
    setHasAttemptedConnection(false);
    if (activeSession) {
      setConnectionAttemptedForSession(activeSession.id);
    }
    connect();
  });

  // // Handler for retry last action (for errors)
  // const handleRetryLastAction = useEvent(() => {
  //   // Could implement logic to retry the last failed action
  //   // For now, just log that retry was requested
  //   console.log("Retry last action requested");
  // });

  // // Handler for dismiss error
  // const handleDismissError = useEvent((errorId: string) => {
  //   // Could implement logic to dismiss/hide specific errors
  //   // For now, just log that dismiss was requested
  //   console.log("Dismiss error requested for:", errorId);
  // });

  const hasNotifications = notifications.length > 0;
  const hasActiveSessions = sessionState.sessions.length > 0;

  if (!hasActiveSessions) {
    return (
      <EmptyState
        currentAgentId={activeSession?.agentId}
        connectionState={connectionState}
        onConnect={handleManualConnect}
        onDisconnect={handleManualDisconnect}
      />
    );
  }

  return (
    <div className="flex flex-col flex-1 overflow-hidden mo-agent-panel">
      <AgentPanelHeader
        connectionState={connectionState}
        currentAgentId={activeSession?.agentId}
        onConnect={handleManualConnect}
        onDisconnect={handleManualDisconnect}
      />
      <SessionTabs />

      <ChatContent
        hasNotifications={hasNotifications}
        connectionState={connectionState}
        notifications={notifications}
        pendingPermission={pendingPermission}
        onResolvePermission={resolvePermission}
        onRetryConnection={handleRetryConnection}
        // onRetryLastAction={handleRetryLastAction}
        // onDismissError={handleDismissError}
      />

      <LoadingIndicator
        isLoading={isLoading}
        isRequestingPermission={!!pendingPermission}
        onStop={handleStop}
      />

      <PromptArea
        isLoading={isLoading}
        currentSession={currentSession}
        promptValue={promptValue}
        onPromptValueChange={setPromptValue}
        onPromptSubmit={handlePromptSubmit}
      />
    </div>
  );
};

export default AgentPanel;
