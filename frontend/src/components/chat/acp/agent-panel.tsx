/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { capitalize } from "lodash-es";
import {
  AtSignIcon,
  BotMessageSquareIcon,
  PaperclipIcon,
  RefreshCwIcon,
  SendIcon,
  SquareIcon,
  StopCircleIcon,
} from "lucide-react";
import React, { memo, useEffect, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { useAcpClient } from "use-acp";
import {
  ConnectionStatus,
  PermissionRequest,
} from "@/components/chat/acp/common";
import {
  type AdditionalCompletions,
  PromptInput,
} from "@/components/editor/ai/add-cell-with-ai";
import { PanelEmptyState } from "@/components/editor/chrome/panels/empty-state";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
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
import type { Completion } from "@codemirror/autocomplete";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type {
  ContentBlock,
  RequestPermissionResponse,
} from "@zed-industries/agent-client-protocol";
import {
  addContextCompletion,
  CONTEXT_TRIGGER,
} from "@/components/editor/ai/completion-utils";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
} from "@/components/ui/select";
import { toast } from "@/components/ui/use-toast";
import { DelayMount } from "@/components/utils/delay-mount";
import { useRequestClient } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { Functions } from "@/utils/functions";
import { Paths } from "@/utils/paths";
import { FileAttachmentPill } from "../chat-components";
import { ReadyToChatBlock } from "./blocks";
import {
  convertFilesToResourceLinks,
  parseContextFromPrompt,
} from "./context-utils";
import { getAgentPrompt } from "./prompt";
import type {
  AgentConnectionState,
  AgentPendingPermission,
  AvailableCommands,
  ExternalAgentSessionId,
  NotificationEvent,
  SessionMode,
} from "./types";

const logger = Logger.get("agents");

// File attachment constants
const SUPPORTED_ATTACHMENT_TYPES = ["image/*", "text/*"];

interface AgentTitleProps {
  currentAgentId?: ExternalAgentId;
}

const AgentTitle = memo<AgentTitleProps>(({ currentAgentId }) => (
  <span className="text-sm font-medium">{capitalize(currentAgentId)}</span>
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
      {currentAgentId && <AgentTitle currentAgentId={currentAgentId} />}
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
  ({ currentAgentId, connectionState, onConnect, onDisconnect }) => {
    const filename = useAtomValue(filenameAtom);
    return (
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
                description={
                  <>
                    Start agents by running these commands in your terminal:
                    <br />
                    Note: This must be in the directory{" "}
                    {Paths.dirname(filename ?? "")}
                  </>
                }
              />
            )}
          </div>
        </div>
      </div>
    );
  },
);
EmptyState.displayName = "EmptyState";

interface LoadingIndicatorProps {
  isLoading: boolean;
  isRequestingPermission: boolean;
  onStop: () => void;
}

const LoadingIndicator = memo<LoadingIndicatorProps>(
  ({ isLoading, isRequestingPermission, onStop }) => {
    if (!isLoading) {
      return null;
    }

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
  commands: AvailableCommands | undefined;
  onPromptValueChange: (value: string) => void;
  onPromptSubmit: (e: KeyboardEvent | undefined, prompt: string) => void;
  onAddFiles: (files: File[]) => void;
  onStop: () => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  sessionMode?: SessionMode;
  onModeChange?: (mode: string) => void;
}

const PromptArea = memo<PromptAreaProps>(
  ({
    isLoading,
    activeSessionId,
    promptValue,
    commands,
    onPromptValueChange,
    onPromptSubmit,
    onAddFiles,
    onStop,
    fileInputRef,
    sessionMode,
    onModeChange,
  }) => {
    const inputRef = useRef<ReactCodeMirrorRef | null>(null);
    const promptCompletions: AdditionalCompletions | undefined = useMemo(() => {
      if (!commands) {
        return undefined;
      }
      // sentence has to begin with '/' to trigger autocomplete
      return {
        triggerCompletionRegex: /^\/(\w+)?/,
        completions: commands.map(
          (prompt): Completion => ({
            label: `/${prompt.name}`,
            info: prompt.description,
          }),
        ),
      };
    }, [commands]);

    const handleSendClick = useEvent(() => {
      if (promptValue.trim()) {
        onPromptSubmit(undefined, promptValue);
      }
    });

    const handleAddContext = useEvent(() => {
      // For now, just append @ to the current value
      addContextCompletion(inputRef);
    });

    return (
      <div className="border-t bg-background flex-shrink-0">
        <div
          className={cn(
            "px-3 py-2 min-h-[80px]",
            (isLoading || !activeSessionId) && "opacity-50 pointer-events-none",
          )}
        >
          <PromptInput
            inputRef={inputRef}
            value={promptValue}
            onChange={isLoading ? Functions.NOOP : onPromptValueChange}
            onSubmit={onPromptSubmit}
            additionalCompletions={promptCompletions}
            onClose={Functions.NOOP}
            onAddFiles={onAddFiles}
            placeholder={
              isLoading
                ? "Processing..."
                : `Ask anything, ${CONTEXT_TRIGGER} to include context about tables or dataframes`
            }
            className={isLoading ? "opacity-50 pointer-events-none" : ""}
            maxHeight="120px"
          />
        </div>
        <TooltipProvider>
          <div className="px-3 py-2 border-t border-border/20 flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              {sessionMode && onModeChange && (
                <ModeSelector
                  sessionMode={sessionMode}
                  onModeChange={onModeChange}
                />
              )}
            </div>
            <div className="flex flex-row">
              <Tooltip content="Add context">
                <Button
                  variant="text"
                  size="icon"
                  onClick={handleAddContext}
                  disabled={isLoading}
                >
                  <AtSignIcon className="h-3.5 w-3.5" />
                </Button>
              </Tooltip>
              <Tooltip content="Attach a file">
                <Button
                  variant="text"
                  size="icon"
                  className="cursor-pointer"
                  onClick={() => fileInputRef.current?.click()}
                  title="Attach a file"
                  disabled={isLoading}
                >
                  <PaperclipIcon className="h-3.5 w-3.5" />
                </Button>
              </Tooltip>
              <Input
                ref={fileInputRef}
                type="file"
                multiple={true}
                hidden={true}
                onChange={(event) => {
                  if (event.target.files) {
                    onAddFiles([...event.target.files]);
                  }
                }}
                accept={SUPPORTED_ATTACHMENT_TYPES.join(",")}
              />
              <Tooltip content={isLoading ? "Stop" : "Submit"}>
                <Button
                  variant="text"
                  size="sm"
                  className="h-6 w-6 p-0 hover:bg-muted/30 cursor-pointer"
                  onClick={isLoading ? onStop : handleSendClick}
                  disabled={isLoading ? false : !promptValue.trim()}
                >
                  {isLoading ? (
                    <SquareIcon className="h-3 w-3 fill-current" />
                  ) : (
                    <SendIcon className="h-3 w-3" />
                  )}
                </Button>
              </Tooltip>
            </div>
          </div>
        </TooltipProvider>
      </div>
    );
  },
);
PromptArea.displayName = "PromptArea";

interface ModeSelectorProps {
  sessionMode: SessionMode;
  onModeChange: (mode: string) => void;
}

const ModeSelector = memo<ModeSelectorProps>(
  ({ sessionMode, onModeChange }) => {
    const availableModes = sessionMode?.availableModes || [];
    const currentModeId = sessionMode?.currentModeId;
    if (availableModes.length === 0) {
      return null;
    }

    const modeOptions = availableModes.map((mode) => ({
      value: mode.id,
      label: mode.name,
      subtitle: mode.description ?? "",
    }));
    const currentMode = modeOptions.find((opt) => opt.value === currentModeId);

    return (
      <Select value={currentModeId} onValueChange={onModeChange}>
        <SelectTrigger className="h-6 text-xs border-border shadow-none! ring-0! bg-muted hover:bg-muted/30 py-0 px-2 gap-1 capitalize">
          {currentMode?.label ?? currentModeId}
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Agent Mode</SelectLabel>
            {modeOptions.map((option) => (
              <SelectItem
                key={option.value}
                value={option.value}
                className="text-xs"
              >
                <div className="flex flex-col">
                  {option.label}
                  {option.subtitle && (
                    <div className="text-muted-foreground text-xs pt-1 block">
                      {option.subtitle}
                    </div>
                  )}
                </div>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    );
  },
);
ModeSelector.displayName = "ModeSelector";

interface ChatContentProps {
  hasNotifications: boolean;
  agentId: ExternalAgentId | undefined;
  connectionState: AgentConnectionState;
  sessionId: ExternalAgentSessionId | null;
  notifications: NotificationEvent[];
  pendingPermission: AgentPendingPermission;
  onResolvePermission: (option: RequestPermissionResponse) => void;
  onRetryConnection?: () => void;
  onRetryLastAction?: () => void;
  onDismissError?: (errorId: string) => void;
}

const ChatContent = memo<ChatContentProps>(
  ({
    hasNotifications,
    agentId,
    connectionState,
    notifications,
    pendingPermission,
    onResolvePermission,
    onRetryConnection,
    onRetryLastAction,
    onDismissError: _onDismissError,
    sessionId,
  }) => {
    const [isScrolledToBottom, setIsScrolledToBottom] = useState(true);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const isDisconnected = connectionState.status === "disconnected";

    // Scroll handler to determine if we're at the bottom of the chat
    const handleScroll = useEvent(() => {
      const container = scrollContainerRef.current;
      if (!container) {
        return;
      }

      const { scrollTop, scrollHeight, clientHeight } = container;
      const hasOverflow = scrollHeight > clientHeight;
      const isAtBottom = hasOverflow
        ? Math.abs(scrollHeight - clientHeight - scrollTop) < 5
        : true; // 5px threshold
      setIsScrolledToBottom(isAtBottom);
    });

    const scrollToBottom = useEvent(() => {
      const container = scrollContainerRef.current;
      if (!container) {
        return;
      }

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

    const renderThread = () => {
      if (hasNotifications) {
        return (
          <AgentThread
            isConnected={connectionState.status === "connected"}
            notifications={notifications}
            onRetryConnection={onRetryConnection}
            onRetryLastAction={onRetryLastAction}
          />
        );
      }

      const isConnected = connectionState.status === "connected";
      if (isConnected) {
        return <ReadyToChatBlock />;
      }

      return (
        <div className="flex items-center justify-center h-full min-h-[200px] flex-col">
          <PanelEmptyState
            title="Waiting for agent"
            description="Your AI agent will appear here when active"
            icon={<BotMessageSquareIcon />}
          />
          {isDisconnected && agentId && (
            <AgentDocs
              className="border-t pt-6 px-5"
              title="Make sure you're connected to an agent"
              description="Run this command in your terminal:"
              agents={[agentId]}
            />
          )}
          {isDisconnected && (
            <Button
              variant="outline"
              onClick={onRetryConnection}
              type="button"
              className="mt-4"
            >
              Retry
            </Button>
          )}
        </div>
      );
    };

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
          {renderThread()}
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
  return Paths.dirname(filename);
}

const AgentPanel: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [promptValue, setPromptValue] = useState("");
  const [files, setFiles] = useState<File[]>();
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      readTextFile: (request) => {
        logger.debug("Agent requesting file read", {
          path: request.path,
        });
        return sendFileDetails({ path: request.path }).then((response) => ({
          content: response.contents || "",
        }));
      },
      writeTextFile: (request) => {
        logger.debug("Agent requesting file write", {
          path: request.path,
          contentLength: request.content.length,
        });
        return sendUpdateFile({
          path: request.path,
          contents: request.content,
        }).then(() => ({}));
      },
    },
    autoConnect: false, // We'll manage connection manually based on active session
  });

  const {
    connect,
    disconnect,
    setActiveSessionId,
    connectionState,
    notifications,
    pendingPermission,
    availableCommands,
    resolvePermission,
    sessionMode,
    activeSessionId,
    agent,
  } = acpClient;

  useEffect(() => {
    agent?.initialize({
      protocolVersion: 1,
      clientCapabilities: {
        fs: {
          readTextFile: true,
          writeTextFile: true,
        },
      },
    });
  }, [agent]);

  // Auto-connect to agent when we have an active session, but only once per session
  useEffect(() => {
    setActiveSessionId(null);

    if (wsUrl === NO_WS_SET) {
      return;
    }

    logger.debug("Auto-connecting to agent", {
      sessionId: activeSessionId,
    });
    void connect().catch((error) => {
      logger.error("Failed to connect to agent", { error });
    });

    return () => {
      // We don't want to disconnect so users can switch between different
      // panels without losing their session
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrl]);

  const handleNewSession = useEvent(async () => {
    if (!agent) {
      return;
    }

    // If there is an active session, we should stop it
    if (activeSessionId) {
      setActiveSessionId(null);
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
        if (tabLastActiveSessionId) {
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
        } else {
          // No existing session, create new one
          await handleNewSession();
        }
      } catch (error) {
        logger.error("Failed to create or resume session:", error);
      }
    };

    createOrResumeSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, agent, tabLastActiveSessionId, activeSessionId]);

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
      setFiles(undefined);

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

      const promptBlocks: ContentBlock[] = [{ type: "text", text: prompt }];

      // Parse context from the prompt
      const { contextBlocks, attachmentBlocks } =
        await parseContextFromPrompt(prompt);
      promptBlocks.push(...contextBlocks, ...attachmentBlocks);

      // Add manually uploaded files as resource links
      if (files && files.length > 0) {
        const fileResourceLinks = await convertFilesToResourceLinks(files);
        promptBlocks.push(...fileResourceLinks);
      }

      const hasGivenRules = notifications.some(
        (notification) =>
          notification.type === "session_notification" &&
          notification.data.update.sessionUpdate === "user_message_chunk",
      );
      if (!hasGivenRules) {
        promptBlocks.push(
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
              mimeType: "text/plain",
              text: getAgentPrompt(filename),
            },
          },
        );
      }

      try {
        await agent.prompt({
          sessionId: activeSessionId,
          prompt: promptBlocks,
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

  // Handler for adding files
  const handleAddFiles = useEvent((newFiles: File[]) => {
    if (newFiles.length === 0) {
      return;
    }
    setFiles((prev) => [...(prev ?? []), ...newFiles]);
  });

  // Handler for removing files
  const handleRemoveFile = useEvent((fileToRemove: File) => {
    if (files) {
      setFiles(files.filter((f) => f !== fileToRemove));
    }
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

  const handleModeChange = useEvent((mode: string) => {
    logger.debug("Mode change requested", {
      sessionId: activeSessionId,
      mode,
    });
    if (!agent) {
      toast({
        title: "Agent not connected",
        description: "Please connect to an agent to change the mode",
        variant: "danger",
      });
      return;
    }
    if (!agent.setSessionMode) {
      toast({
        title: "Mode change not supported",
        description: "The agent does not support mode changes",
        variant: "danger",
      });
      return;
    }
    void agent.setSessionMode?.({
      sessionId: activeSessionId as string,
      modeId: mode,
    });
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

  const renderBody = () => {
    const isConnecting = connectionState.status === "connecting";
    const delay = 200; // ms
    if (isConnecting) {
      return (
        <DelayMount milliseconds={delay}>
          <div className="flex items-center justify-center h-full min-h-[200px] flex-col">
            <Spinner size="medium" className="text-primary" />
            <span className="text-sm text-muted-foreground">
              Connecting to the agent...
            </span>
          </div>
        </DelayMount>
      );
    }

    const isLoadingSession =
      tabLastActiveSessionId == null && connectionState.status === "connected";
    if (isLoadingSession) {
      return (
        <DelayMount milliseconds={delay}>
          <div className="flex items-center justify-center h-full min-h-[200px] flex-col">
            <Spinner size="medium" className="text-primary" />
            <span className="text-sm text-muted-foreground">
              Creating a new session...
            </span>
          </div>
        </DelayMount>
      );
    }

    return (
      <>
        <ChatContent
          key={activeSessionId}
          agentId={selectedTab?.agentId}
          sessionId={selectedTab?.externalAgentSessionId ?? null}
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

        {files && files.length > 0 && (
          <div className="flex flex-row gap-1 flex-wrap p-3 border-t">
            {files.map((file) => (
              <FileAttachmentPill
                file={file}
                key={file.name}
                onRemove={() => handleRemoveFile(file)}
              />
            ))}
          </div>
        )}

        <PromptArea
          isLoading={isLoading}
          activeSessionId={activeSessionId}
          promptValue={promptValue}
          onPromptValueChange={setPromptValue}
          onPromptSubmit={handlePromptSubmit}
          onAddFiles={handleAddFiles}
          onStop={handleStop}
          fileInputRef={fileInputRef}
          commands={availableCommands}
          sessionMode={sessionMode}
          onModeChange={handleModeChange}
        />
      </>
    );
  };

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

      {renderBody()}
    </div>
  );
};

export default AgentPanel;
