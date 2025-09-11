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
  ReadTextFileRequest,
  ReadTextFileResponse,
  WriteTextFileRequest,
  WriteTextFileResponse,
} from "@zed-industries/agent-client-protocol";
import { toast } from "@/components/ui/use-toast";
import { useRequestClient } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { getAgentPrompt } from "./prompt";
import type { AgentConnectionState } from "./types";

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
  connectionState: AgentConnectionState;
  currentAgentId?: ExternalAgentId;
  onConnect: () => void;
  onDisconnect: () => void;
  onRestartThread?: () => void;
  hasActiveSession?: boolean;
}

const AgentPanelHeader = memo<AgentPanelHeaderProps>(
  ({
    connectionState,
    currentAgentId,
    onConnect,
    onDisconnect,
    onRestartThread,
    hasActiveSession,
  }) => (
    <div className="flex border-b px-3 py-2 justify-between shrink-0 items-center">
      <HeaderInfo
        currentAgentId={currentAgentId}
        connectionStatus={connectionState.status}
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
        <ConnectionControl
          connectionState={connectionState}
          onConnect={onConnect}
          onDisconnect={onDisconnect}
        />
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
  activeSessionId: string | null;
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
  connectionState: AgentConnectionState;
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
  const [isLoading, setIsLoading] = useState(false);
  const [promptValue, setPromptValue] = useState("");
  const [hasAttemptedConnection, setHasAttemptedConnection] = useState(false);
  const [connectionAttemptedForSession, setConnectionAttemptedForSession] =
    useState<string | null>(null);

  const [activeSession] = useAtom(selectedTabAtom);
  const [sessionState, setSessionState] = useAtom(agentSessionStateAtom);

  const wsUrl = activeSession
    ? getAgentWebSocketUrl(activeSession.agentId)
    : "ws://localhost:8000/message";
  const { sendUpdateFile, sendFileDetails } = useRequestClient();

  const acpClient = useAcpClient({
    wsUrl,
    clientOptions: {
      readTextFile: (
        request: ReadTextFileRequest,
      ): Promise<ReadTextFileResponse> => {
        logger.debug("Agent requesting file read", {
          path: request.path,
          sessionId: activeSession?.tabId,
        });
        return sendFileDetails({ path: request.path }).then((response) => ({
          content: response.contents || "",
        }));
      },
      writeTextFile: (
        request: WriteTextFileRequest,
      ): Promise<WriteTextFileResponse> => {
        logger.debug("Agent requesting file write", {
          path: request.path,
          contentLength: request.content.length,
          sessionId: activeSession?.tabId,
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

  // Auto-connect when we have an active session, but only once per session
  useEffect(() => {
    if (
      activeSession &&
      connectionState.status === "disconnected" &&
      !hasAttemptedConnection &&
      connectionAttemptedForSession !== activeSession.tabId
    ) {
      logger.debug("Auto-connecting to agent", {
        sessionId: activeSession.tabId,
        agentId: activeSession.agentId,
        connectionAttemptedFor: connectionAttemptedForSession,
      });
      setHasAttemptedConnection(true);
      setConnectionAttemptedForSession(activeSession.tabId);
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
    if (
      activeSession &&
      connectionAttemptedForSession !== activeSession.tabId
    ) {
      logger.debug(
        "Active session changed, resetting connection attempt tracking",
        {
          previousSessionId: connectionAttemptedForSession,
          newSessionId: activeSession.tabId,
          agentId: activeSession.agentId,
        },
      );
      setHasAttemptedConnection(false);
    }
  }, [activeSession, connectionAttemptedForSession]);

  // Reset connection attempt tracking on successful connection
  useEffect(() => {
    if (connectionState.status === "connected") {
      logger.debug("Connection established, resetting attempt tracking", {
        sessionId: activeSession?.tabId,
        agentId: activeSession?.agentId,
      });
      setHasAttemptedConnection(false);
    }
  }, [connectionState.status, activeSession]);

  // Create or resume a session when successfully connected
  useEffect(() => {
    if (
      connectionState.status === "connected" &&
      agent &&
      activeSession &&
      !activeSessionId
    ) {
      const createOrResumeSession = async () => {
        try {
          let sessionId: string;
          const newSessionRequest = {
            cwd: "",
            mcpServers: [],
          };

          // Check if we need to create a new session
          if (!activeSession.externalAgentSessionId) {
            // No existing session, create new one
            logger.debug("Creating new agent session (no existing session)", {
              sessionId: activeSession.tabId,
              agentId: activeSession.agentId,
            });
            await agent.initialize({
              clientCapabilities: {
                fs: {
                  readTextFile: true,
                  writeTextFile: true,
                },
              },
              protocolVersion: 1,
            });
            const newSession = await agent.newSession(newSessionRequest);
            sessionId = newSession.sessionId;

            // Update our state with the new external agent session ID
            logger.debug(
              "Updating session state with new external agent session ID",
              {
                sessionId: activeSession.tabId,
                externalSessionId: sessionId,
              },
            );
            setSessionState((prev) =>
              updateSessionExternalAgentSessionId(
                prev,
                activeSession.tabId,
                sessionId as any,
              ),
            );
          } else {
            // Try to resume existing session
            try {
              logger.debug("Attempting to resume existing agent session", {
                sessionId: activeSession.tabId,
                externalSessionId: activeSession.externalAgentSessionId,
                agentId: activeSession.agentId,
              });
              await agent.loadSession?.({
                sessionId: activeSession.externalAgentSessionId,
                ...newSessionRequest,
              });

              sessionId = activeSession.externalAgentSessionId;
              logger.debug("Successfully resumed agent session", {
                sessionId: activeSession.tabId,
                externalSessionId: sessionId,
                agentId: activeSession.agentId,
              });
            } catch (resumeError) {
              logger.debug("Failed to resume session, creating new session", {
                sessionId: activeSession.tabId,
                externalSessionId: activeSession.externalAgentSessionId,
                error: resumeError,
              });
              // Fall back to creating new session
              const newSession = await agent.newSession(newSessionRequest);
              sessionId = newSession.sessionId;

              // Update our state with the new external agent session ID
              logger.debug(
                "Updating session state after fallback session creation",
                {
                  sessionId: activeSession.tabId,
                  newExternalSessionId: sessionId,
                },
              );
              setSessionState((prev) =>
                updateSessionExternalAgentSessionId(
                  prev,
                  activeSession.tabId,
                  sessionId as any,
                ),
              );
            }
          }

          logger.debug("Setting current session", {
            sessionId: activeSession.tabId,
            externalSessionId: sessionId,
            agentId: activeSession.agentId,
          });
        } catch (error) {
          logger.error("Failed to create or resume session:", error);
        }
      };

      createOrResumeSession();
    }
    // Reset session when disconnected
    if (connectionState.status === "disconnected") {
      logger.debug("Connection disconnected, clearing current session", {
        previousSession: activeSessionId,
        activeSessionId: activeSession?.tabId,
      });
    }
  }, [
    connectionState.status,
    agent,
    activeSession,
    activeSessionId,
    setSessionState,
  ]);

  // Handler for prompt submission
  const handlePromptSubmit = useEvent(
    async (_e: KeyboardEvent | undefined, prompt: string) => {
      if (!activeSessionId || !agent || isLoading || !activeSession) {
        logger.debug("Prompt submit blocked", {
          hasActiveSessionId: !!activeSessionId,
          hasAgent: !!agent,
          isLoading,
          hasActiveSession: !!activeSession,
        });
        return;
      }

      logger.debug("Submitting prompt to agent", {
        sessionId: activeSession.tabId,
        externalSessionId: activeSessionId,
        promptLength: prompt.length,
        promptPreview: prompt.substring(0, 100),
      });
      setIsLoading(true);
      setPromptValue("");

      // Update session title with first message if it's still the default
      if (activeSession.title.startsWith("New ")) {
        logger.debug("Updating session title with first message", {
          sessionId: activeSession.tabId,
          oldTitle: activeSession.title,
          newTitle: prompt.substring(0, 50),
        });
        setSessionState((prev) =>
          updateSessionTitle(prev, activeSession.tabId, prompt),
        );
      }

      const filename = store.get(filenameAtom);
      if (!filename) {
        logger.debug("Prompt submission failed: notebook not named");
        toast({
          title: "Notebook must be named",
          description: "Please name the notebook to use the agent",
          variant: "danger",
        });
        return;
      }

      logger.debug("Sending prompt to agent", {
        sessionId: activeSession.tabId,
        externalSessionId: activeSessionId,
        filename,
      });

      try {
        await agent.prompt({
          sessionId: activeSessionId,
          prompt: [{ type: "text", text: getAgentPrompt(prompt, filename) }],
        });
        logger.debug("Prompt sent successfully", {
          sessionId: activeSession.tabId,
          externalSessionId: activeSessionId,
        });
      } catch (error) {
        logger.error("Failed to send prompt", {
          sessionId: activeSession.tabId,
          externalSessionId: activeSessionId,
          error,
        });
      } finally {
        logger.debug("Setting loading state to false after prompt submission");
        setIsLoading(false);
      }
    },
  );

  // Handler for stopping the current operation
  const handleStop = useEvent(() => {
    if (!activeSessionId) {
      logger.debug("Stop requested but no current session");
      return;
    }
    logger.debug("Stopping current agent operation", {
      sessionId: activeSession?.tabId,
      externalSessionId: activeSessionId,
    });
    agent?.cancel({ sessionId: activeSessionId });
    setIsLoading(false);
  });

  // Handler for manual connect - allows retry after failed auto-connect
  const handleManualConnect = useEvent(() => {
    logger.debug("Manual connect requested", {
      sessionId: activeSession?.tabId,
      agentId: activeSession?.agentId,
      currentStatus: connectionState.status,
    });
    setHasAttemptedConnection(false);
    if (activeSession) {
      setConnectionAttemptedForSession(activeSession.tabId);
    }
    connect();
  });

  // Handler for manual disconnect
  const handleManualDisconnect = useEvent(() => {
    logger.debug("Manual disconnect requested", {
      sessionId: activeSession?.tabId,
      agentId: activeSession?.agentId,
      currentStatus: connectionState.status,
    });
    disconnect();
  });

  // Handler for retry connection from error/connection components
  const handleRetryConnection = useEvent(() => {
    logger.debug("Retry connection requested", {
      sessionId: activeSession?.tabId,
      agentId: activeSession?.agentId,
      currentStatus: connectionState.status,
    });
    setHasAttemptedConnection(false);
    if (activeSession) {
      setConnectionAttemptedForSession(activeSession.tabId);
    }
    connect();
  });

  // Handler for restarting the thread (creates new session)
  const handleRestartThread = useEvent(async () => {
    if (!activeSession || !agent || isLoading) {
      logger.debug("Restart thread blocked", {
        hasActiveSession: !!activeSession,
        hasAgent: !!agent,
        isLoading,
      });
      return;
    }

    logger.debug("Restarting thread - creating new session", {
      sessionId: activeSession.tabId,
      agentId: activeSession.agentId,
      currentExternalSessionId: activeSession.externalAgentSessionId,
    });
    setIsLoading(true);

    try {
      // Create new session
      logger.debug("Creating new session for thread restart", {
        sessionId: activeSession.tabId,
        agentId: activeSession.agentId,
      });
      const newSessionRequest = {
        cwd: "",
        mcpServers: [],
      };
      const newSession = await agent.newSession(newSessionRequest);
      const sessionId = newSession.sessionId;

      // Update our state with the new external agent session ID
      logger.debug("Updating session state after thread restart", {
        sessionId: activeSession.tabId,
        newExternalSessionId: sessionId,
      });
      setSessionState((prev) =>
        updateSessionExternalAgentSessionId(
          prev,
          activeSession.tabId,
          sessionId as any,
        ),
      );

      logger.debug("Thread restart completed successfully", {
        sessionId: activeSession.tabId,
        newExternalSessionId: sessionId,
      });
    } catch (error) {
      logger.error("Failed to restart thread", {
        sessionId: activeSession.tabId,
        agentId: activeSession.agentId,
        error,
      });
    } finally {
      logger.debug(
        "Setting loading state to false after thread restart attempt",
      );
      setIsLoading(false);
    }
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

  // Log state changes for debugging
  useEffect(() => {
    logger.debug("Agent panel state update", {
      hasActiveSessions,
      hasNotifications,
      notificationCount: notifications.length,
      connectionStatus: connectionState.status,
      activeSessionId: activeSession?.tabId,
      isLoading,
    });
  }, [
    hasActiveSessions,
    hasNotifications,
    notifications.length,
    connectionState.status,
    activeSession?.tabId,
    activeSessionId,
    isLoading,
  ]);

  if (!hasActiveSessions) {
    logger.debug("Rendering empty state - no active sessions");
    return (
      <EmptyState
        currentAgentId={activeSession?.agentId}
        connectionState={connectionState}
        onConnect={handleManualConnect}
        onDisconnect={handleManualDisconnect}
      />
    );
  }

  logger.debug("Rendering main agent panel", {
    activeSessionId: activeSession?.tabId,
    agentId: activeSession?.agentId,
    connectionStatus: connectionState.status,
    hasNotifications,
  });

  return (
    <div className="flex flex-col flex-1 overflow-hidden mo-agent-panel">
      <AgentPanelHeader
        connectionState={connectionState}
        currentAgentId={activeSession?.agentId}
        onConnect={handleManualConnect}
        onDisconnect={handleManualDisconnect}
        onRestartThread={handleRestartThread}
        hasActiveSession={true}
      />
      <SessionTabs />

      <ChatContent
        hasNotifications={hasNotifications}
        connectionState={connectionState}
        notifications={notifications}
        pendingPermission={pendingPermission}
        onResolvePermission={(option) => {
          logger.debug("Resolving permission request", {
            sessionId: activeSession?.tabId,
            option,
            pendingPermission,
          });
          resolvePermission(option);
        }}
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
        activeSessionId={activeSessionId}
        promptValue={promptValue}
        onPromptValueChange={setPromptValue}
        onPromptSubmit={handlePromptSubmit}
      />
    </div>
  );
};

export default AgentPanel;
