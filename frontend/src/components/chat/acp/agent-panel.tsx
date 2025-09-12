/* Copyright 2025 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { capitalize } from "lodash-es";
import {
  BotMessageSquareIcon,
  RefreshCwIcon,
  StopCircleIcon,
} from "lucide-react";
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
import { AgentDocs } from "./agent-docs";
import { AgentSelector } from "./agent-selector";
import ScrollToBottomButton from "./scroll-to-bottom-button";
import { SessionTabs } from "./session-tabs";
import {
  agentSessionStateAtom,
  type ExternalAgentId,
  getAgentWebSocketUrl,
  selectedTabAtom,
  updateSessionExternalAgentSessionId,
  updateSessionTitle,
} from "./state";
import { AgentThread } from "./thread";
import "./agent-panel.css";
import type {
  ReadTextFileResponse,
  WriteTextFileResponse,
} from "@zed-industries/agent-client-protocol";
import { toast } from "@/components/ui/use-toast";
import { useRequestClient } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { Paths } from "@/utils/paths";
import { getAgentPrompt } from "./prompt";
import type {
  AgentConnectionState,
  AgentPendingPermission,
  ExternalAgentSessionId,
  NotificationEvent,
} from "./types";

const logger = Logger.get("agents");

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
  connectionState: AgentConnectionState;
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
  shouldShowConnectionControl?: boolean;
}

const HeaderInfo = memo<HeaderInfoProps>(
  ({ currentAgentId, connectionStatus, shouldShowConnectionControl }) => (
    <div className="flex items-center gap-2">
      <BotMessageSquareIcon className="h-4 w-4 text-muted-foreground" />
      <AgentTitle currentAgentId={currentAgentId} />
      {shouldShowConnectionControl && (
        <ConnectionStatus status={connectionStatus} />
      )}
    </div>
  ),
);
HeaderInfo.displayName = "HeaderInfo";

interface AgentPanelHeaderProps {
  connectionState: AgentConnectionState;
  currentAgentId?: ExternalAgentId;
  onConnect: () => void;
  onDisconnect: () => void;
  onRestartThread?: () => void;
  hasActiveSession?: boolean;
  shouldShowConnectionControl?: boolean;
}

const AgentPanelHeader = memo<AgentPanelHeaderProps>(
  ({
    connectionState,
    currentAgentId,
    onConnect,
    onDisconnect,
    onRestartThread,
    hasActiveSession,
    shouldShowConnectionControl,
  }) => (
    <div className="flex border-b px-3 py-2 justify-between shrink-0 items-center">
      <HeaderInfo
        currentAgentId={currentAgentId}
        connectionStatus={connectionState.status}
        shouldShowConnectionControl={shouldShowConnectionControl}
      />
      <div className="flex items-center gap-2">
        {hasActiveSession &&
          connectionState.status === "connected" &&
          onRestartThread && (
            <Button
              variant="outline"
              size="xs"
              onClick={onRestartThread}
              title="Restart thread (create new session)"
            >
              <RefreshCwIcon className="h-3 w-3 mr-1" />
              Restart
            </Button>
          )}

        {shouldShowConnectionControl && (
          <ConnectionControl
            connectionState={connectionState}
            onConnect={onConnect}
            onDisconnect={onDisconnect}
          />
        )}
      </div>
    </div>
  ),
);
AgentPanelHeader.displayName = "AgentPanelHeader";

interface EmptyStateProps {
  currentAgentId?: ExternalAgentId;
  connectionState: AgentConnectionState;
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
        hasActiveSession={false}
      />
      <SessionTabs />
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-md w-full space-y-6">
          <PanelEmptyState
            title="No Agent Sessions"
            description="Create a new session to start a conversation"
            action={<AgentSelector className="border-y-1 rounded" />}
            icon={<BotMessageSquareIcon />}
          />
          {connectionState.status === "disconnected" && (
            <AgentDocs
              className="border-t pt-6"
              title="Connect to an agent"
              description="Start agents by running these commands in your terminal:"
            />
          )}
        </div>
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
  activeSessionId: ExternalAgentSessionId | null;
  promptValue: string;
  onPromptValueChange: (value: string) => void;
  onPromptSubmit: (e: KeyboardEvent | undefined, prompt: string) => void;
}

const PromptArea = memo<PromptAreaProps>(
  ({
    isLoading,
    activeSessionId,
    promptValue,
    onPromptValueChange,
    onPromptSubmit,
  }) => (
    <div
      className={cn(
        "px-3 py-2 border-t bg-background flex-shrink-0 min-h-[80px]",
        (isLoading || !activeSessionId) && "opacity-50 pointer-events-none",
      )}
    >
      <PromptInput
        value={promptValue}
        onChange={isLoading ? undefined : onPromptValueChange}
        onSubmit={onPromptSubmit}
        onClose={undefined}
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
  connectionState: AgentConnectionState;
  sessionId: ExternalAgentSessionId | null;
  notifications: NotificationEvent[];
  pendingPermission: AgentPendingPermission;
  onResolvePermission: (option: unknown) => void;
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
    sessionId,
  }) => {
    const [isScrolledToBottom, setIsScrolledToBottom] = useState(true);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Scroll handler to determine if we're at the bottom of the chat
    const handleScroll = useEvent(() => {
      const container = scrollContainerRef.current;
      if (!container) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const hasOverflow = scrollHeight > clientHeight;
      const isAtBottom = hasOverflow
        ? Math.abs(scrollHeight - clientHeight - scrollTop) < 5
        : true; // 5px threshold
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
        const timeout = setTimeout(scrollToBottom, 100);
        return () => clearTimeout(timeout);
      }
    }, [notifications.length, isScrolledToBottom, scrollToBottom]);

    return (
      <div className="flex-1 flex flex-col overflow-hidden flex-shrink-0 relative">
        {pendingPermission && (
          <div className="p-3 border-b">
            <PermissionRequest
              permission={pendingPermission}
              onResolve={onResolvePermission}
            />
          </div>
        )}

        <div
          ref={scrollContainerRef}
          className="flex-1 bg-muted/20 w-full flex flex-col overflow-y-auto p-2"
          onScroll={handleScroll}
        >
          {sessionId && (
            <div className="text-xs text-muted-foreground mb-2 px-2">
              Session ID: {sessionId}
            </div>
          )}
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

        <ScrollToBottomButton
          isVisible={!isScrolledToBottom && hasNotifications}
          onScrollToBottom={scrollToBottom}
        />
      </div>
    );
  },
);
ChatContent.displayName = "ChatContent";

const NO_WS_SET = "_skip_auto_connect_";

function getCwd() {
  const filename = store.get(filenameAtom);
  if (!filename) {
    return "";
  }
  return Paths.basename(filename);
}

const AgentPanel: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [promptValue, setPromptValue] = useState("");

  const [selectedTab] = useAtom(selectedTabAtom);
  const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);

  const wsUrl = selectedTab
    ? getAgentWebSocketUrl(selectedTab.agentId)
    : NO_WS_SET;
  const { sendUpdateFile, sendFileDetails } = useRequestClient();
  const isCreatingNewSession = useRef(false);

  const acpClient = useAcpClient({
    wsUrl,
    clientOptions: {
      readTextFile: (request): Promise<ReadTextFileResponse> => {
        logger.debug("Agent requesting file read", {
          path: request.path,
        });
        return sendFileDetails({ path: request.path }).then((response) => ({
          content: response.contents || "",
        }));
      },
      writeTextFile: (request): Promise<WriteTextFileResponse> => {
        logger.debug("Agent requesting file write", {
          path: request.path,
          contentLength: request.content.length,
        });
        return sendUpdateFile({
          path: request.path,
          contents: request.content,
        }).then(() => null);
      },
    },
    autoConnect: false, // We'll manage connection manually based on active session
  });

  const {
    connect,
    disconnect,
    connectionState,
    notifications,
    pendingPermission,
    resolvePermission,
    activeSessionId,
    agent,
  } = acpClient;

  // Auto-connect to agent when we have an active session, but only once per session
  useEffect(() => {
    if (wsUrl === NO_WS_SET) return;

    logger.debug("Auto-connecting to agent", {
      sessionId: activeSessionId,
    });
    connect();

    return () => {
      // We don't want to disconnect so users can switch between different
      // panels without losing their session
    };
  }, [wsUrl, activeSessionId, connect]);

  const handleNewSession = useEvent(async () => {
    if (isCreatingNewSession.current) {
      return;
    }
    if (!agent) {
      return;
    }

    // If there is an active session, we should stop it
    if (activeSessionId) {
      await agent.cancel({ sessionId: activeSessionId }).catch((error) => {
        logger.error("Failed to cancel active session", { error });
      });
    }

    logger.debug("Creating new agent session", {});
    isCreatingNewSession.current = true;
    const newSession = await agent
      .newSession({
        cwd: getCwd(),
        mcpServers: [],
      })
      .finally(() => {
        isCreatingNewSession.current = false;
      });
    setSessionState((prev) =>
      updateSessionExternalAgentSessionId(
        prev,
        newSession.sessionId as ExternalAgentSessionId,
      ),
    );
  });

  const handleResumeSession = useEvent(
    async (previousSessionId: ExternalAgentSessionId) => {
      if (!agent) {
        return;
      }
      logger.debug("Resuming agent session", {
        sessionId: previousSessionId,
      });
      if (!agent.loadSession) {
        throw new Error("Agent does not support loading sessions");
      }
      await agent.loadSession({
        sessionId: previousSessionId,
        cwd: getCwd(),
        mcpServers: [],
      });
      setSessionState((prev) =>
        updateSessionExternalAgentSessionId(prev, previousSessionId),
      );
    },
  );

  // Create or resume a session when successfully connected
  const isConnected = connectionState.status === "connected";
  const tabLastActiveSessionId = selectedTab?.externalAgentSessionId;
  useEffect(() => {
    // No need to do anything if we're not connected, don't have an agent, or don't have a selected tab
    if (!isConnected || !selectedTab || !agent) {
      return;
    }

    // Already have an active session
    if (activeSessionId && tabLastActiveSessionId) {
      return;
    }

    const createOrResumeSession = async () => {
      try {
        // Check if we need to create a new session
        if (!tabLastActiveSessionId) {
          // No existing session, create new one
          await handleNewSession();
        } else {
          // Try to resume existing session
          try {
            await handleResumeSession(tabLastActiveSessionId);
          } catch (resumeError) {
            logger.debug("Failed to resume session, creating new session", {
              externalSessionId: tabLastActiveSessionId,
              error: resumeError,
            });
            // Fall back to creating new session
            await handleNewSession();
          }
        }
      } catch (error) {
        logger.error("Failed to create or resume session:", error);
      }
    };

    createOrResumeSession();
  }, [
    isConnected,
    agent,
    tabLastActiveSessionId,
    activeSessionId,
    handleNewSession,
    handleResumeSession,
    selectedTab,
  ]);

  // Handler for prompt submission
  const handlePromptSubmit = useEvent(
    async (_e: KeyboardEvent | undefined, prompt: string) => {
      if (!activeSessionId || !agent || isLoading) {
        return;
      }

      logger.debug("Submitting prompt to agent", {
        sessionId: activeSessionId,
      });
      setIsLoading(true);
      setPromptValue("");

      // Update session title with first message if it's still the default
      if (selectedTab?.title.startsWith("New ")) {
        setSessionState((prev) => updateSessionTitle(prev, prompt));
      }

      const filename = store.get(filenameAtom);
      if (!filename) {
        toast({
          title: "Notebook must be named",
          description: "Please name the notebook to use the agent",
          variant: "danger",
        });
        return;
      }

      try {
        await agent.prompt({
          sessionId: activeSessionId,
          prompt: [
            { type: "text", text: prompt },
            {
              type: "resource_link",
              uri: filename,
              mimeType: "text/x-python",
              name: filename,
            },
            {
              type: "resource",
              resource: {
                uri: "marimo_rules.md",
                mimeType: "text/markdown",
                text: getAgentPrompt(filename),
              },
            },
          ],
        });
      } catch (error) {
        logger.error("Failed to send prompt", { error });
      } finally {
        setIsLoading(false);
      }
    },
  );

  // Handler for stopping the current operation
  const handleStop = useEvent(async () => {
    if (!activeSessionId || !agent) {
      return;
    }
    await agent.cancel({ sessionId: activeSessionId });
    setIsLoading(false);
  });

  // Handler for manual connect
  const handleManualConnect = useEvent(() => {
    logger.debug("Manual connect requested", {
      currentStatus: connectionState.status,
    });
    connect();
  });

  // Handler for manual disconnect
  const handleManualDisconnect = useEvent(() => {
    logger.debug("Manual disconnect requested", {
      sessionId: activeSessionId,
      currentStatus: connectionState.status,
    });
    disconnect();
  });

  const hasNotifications = notifications.length > 0;
  const hasActiveSessions = sessionState.sessions.length > 0;

  if (!hasActiveSessions) {
    return (
      <EmptyState
        currentAgentId={selectedTab?.agentId}
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
        currentAgentId={selectedTab?.agentId}
        onConnect={handleManualConnect}
        onDisconnect={handleManualDisconnect}
        onRestartThread={handleNewSession}
        hasActiveSession={true}
        shouldShowConnectionControl={wsUrl !== NO_WS_SET}
      />
      <SessionTabs />

      <ChatContent
        sessionId={activeSessionId}
        hasNotifications={hasNotifications}
        connectionState={connectionState}
        notifications={notifications}
        pendingPermission={pendingPermission}
        onResolvePermission={(option) => {
          logger.debug("Resolving permission request", {
            sessionId: activeSessionId,
            option,
          });
          resolvePermission(option);
        }}
        onRetryConnection={handleManualConnect}
      />

      <LoadingIndicator
        isLoading={isLoading}
        isRequestingPermission={!!pendingPermission}
        onStop={handleStop}
      />

      <PromptArea
        isLoading={isLoading}
        activeSessionId={activeSessionId}
        promptValue={promptValue}
        onPromptValueChange={setPromptValue}
        onPromptSubmit={handlePromptSubmit}
      />
    </div>
  );
};

export default AgentPanel;
