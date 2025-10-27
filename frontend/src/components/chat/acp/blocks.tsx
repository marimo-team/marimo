/* Copyright 2024 Marimo. All rights reserved. */

import type {
  ContentBlock,
  ToolCallContent,
  ToolCallLocation,
} from "@zed-industries/agent-client-protocol";
import { capitalize } from "lodash-es";
import {
  BotMessageSquareIcon,
  FileAudio2Icon,
  FileIcon,
  FileImageIcon,
  FileJsonIcon,
  FileTextIcon,
  FileVideoCameraIcon,
  RotateCcwIcon,
  WifiIcon,
  WifiOffIcon,
  WrenchIcon,
  XCircleIcon,
  XIcon,
} from "lucide-react";
import React from "react";
import { JsonRpcError, mergeToolCalls } from "use-acp";
import { ReadonlyDiff } from "@/components/editor/code/readonly-diff";
import { JsonOutput } from "@/components/editor/output/JsonOutput";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { Strings } from "@/utils/strings";
import { MarkdownRenderer } from "../markdown-renderer";
import { SimpleAccordion } from "./common";
import type {
  AgentNotificationEvent,
  AgentThoughtNotificationEvent,
  ConnectionChangeNotificationEvent,
  ContentBlockOf,
  CurrentModeUpdateNotificationEvent,
  ErrorNotificationEvent,
  PlanNotificationEvent,
  SessionNotificationEventData,
  ToolCallNotificationEvent,
  ToolCallUpdateNotificationEvent,
  UserNotificationEvent,
} from "./types";
import {
  isAgentMessages,
  isAgentThoughts,
  isPlans,
  isToolCalls,
  isUserMessages,
} from "./utils";

/**
 * Merges consecutive text blocks into a single text block to prevent
 * fragmented display when agent messages are streamed in chunks.
 */
function mergeConsecutiveTextBlocks(
  contentBlocks: ContentBlock[],
): ContentBlock[] {
  if (contentBlocks.length === 0) {
    return contentBlocks;
  }

  const merged: ContentBlock[] = [];
  let currentTextBlock: string | null = null;

  for (const block of contentBlocks) {
    if (block.type === "text") {
      // Accumulate text content
      if (currentTextBlock === null) {
        currentTextBlock = block.text;
      } else {
        currentTextBlock += block.text;
      }
    } else {
      // If we have accumulated text, flush it before adding non-text block
      if (currentTextBlock !== null) {
        merged.push({ type: "text", text: currentTextBlock });
        currentTextBlock = null;
      }
      merged.push(block);
    }
  }

  // Flush any remaining text
  if (currentTextBlock !== null) {
    merged.push({ type: "text", text: currentTextBlock });
  }

  return merged;
}

export const ErrorBlock = (props: {
  data: ErrorNotificationEvent["data"];
  onRetry?: () => void;
  onDismiss?: () => void;
}) => {
  const error = props.data;
  let message = props.data.message;
  const name = props.data.name;

  // Don't show WebSocket connection errors
  if (message.includes("WebSocket")) {
    return null;
  }

  if (error instanceof JsonRpcError) {
    const dataStr =
      typeof error.data === "string" ? error.data : JSON.stringify(error.data);
    message = `${dataStr} (${error.code})`;
  }

  return (
    <div
      className="border border-[var(--red-6)] bg-[var(--red-2)] rounded-lg p-4 my-2"
      data-block-type="error"
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <XCircleIcon className="h-5 w-5 text-[var(--red-11)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <h4 className="text-sm font-medium text-[var(--red-11)]">
              Agent Error
            </h4>
          </div>
          <div className="text-sm text-[var(--red-11)] leading-relaxed mb-3">
            {message}
          </div>
          <div className="flex items-center gap-2">
            {props.onRetry && (
              <Button
                size="xs"
                variant="outline"
                onClick={props.onRetry}
                className="text-[var(--red-11)] border-[var(--red-6)] hover:bg-[var(--red-3)]"
              >
                <RotateCcwIcon className="h-3 w-3 mr-1" />
                Retry
              </Button>
            )}
            {props.onDismiss && (
              <Button
                size="xs"
                variant="ghost"
                onClick={props.onDismiss}
                className="text-[var(--red-10)] hover:bg-[var(--red-3)]"
              >
                <XIcon className="h-3 w-3 mr-1" />
                Dismiss
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export const ReadyToChatBlock = () => {
  return (
    <div className="flex-1 flex items-center justify-center h-full min-h-[200px] flex-col">
      <div className="text-center space-y-3">
        <div className="w-12 h-12 mx-auto rounded-full bg-[var(--blue-3)] flex items-center justify-center">
          <BotMessageSquareIcon className="h-6 w-6 text-[var(--blue-10)]" />
        </div>
        <div>
          <h3 className="text-lg font-medium text-foreground mb-1">
            Agent is connected
          </h3>
          <p className="text-sm text-muted-foreground">
            You can start chatting with your agent now
          </p>
        </div>
      </div>
    </div>
  );
};

export const ConnectionChangeBlock = (props: {
  data: ConnectionChangeNotificationEvent["data"];
  isConnected: boolean;
  onRetry?: () => void;
  timestamp?: number;
  isOnlyBlock: boolean;
}) => {
  const { status } = props.data;

  if (props.isConnected && props.isOnlyBlock) {
    return <ReadyToChatBlock />;
  }

  const getStatusConfig = () => {
    switch (status) {
      case "connected":
        return {
          icon: <WifiIcon className="h-4 w-4" />,
          title: "Connected to Agent",
          message: "Successfully established connection with the AI agent",
          bgColor: "bg-[var(--blue-2)]",
          borderColor: "border-[var(--blue-6)]",
          textColor: "text-[var(--blue-11)]",
          iconColor: "text-[var(--blue-10)]",
        };
      case "disconnected":
        return {
          icon: <WifiOffIcon className="h-4 w-4" />,
          title: "Disconnected from Agent",
          message: "Connection to the AI agent has been lost",
          bgColor: "bg-[var(--amber-2)]",
          borderColor: "border-[var(--amber-6)]",
          textColor: "text-[var(--amber-11)]",
          iconColor: "text-[var(--amber-10)]",
        };
      case "connecting":
        return {
          icon: <WifiIcon className="h-4 w-4 animate-pulse" />,
          title: "Connecting to Agent",
          message: "Establishing connection with the AI agent...",
          bgColor: "bg-[var(--gray-2)]",
          borderColor: "border-[var(--gray-6)]",
          textColor: "text-[var(--gray-11)]",
          iconColor: "text-[var(--gray-10)]",
        };
      case "error":
        return {
          icon: <WifiOffIcon className="h-4 w-4" />,
          title: "Connection Error",
          message: "Failed to connect to the AI agent",
          bgColor: "bg-[var(--red-2)]",
          borderColor: "border-[var(--red-6)]",
          textColor: "text-[var(--red-11)]",
          iconColor: "text-[var(--red-10)]",
        };
      default:
        return {
          icon: <WifiOffIcon className="h-4 w-4" />,
          title: "Connection Status Changed",
          message: `Agent connection status: ${status}`,
          bgColor: "bg-[var(--gray-2)]",
          borderColor: "border-[var(--gray-6)]",
          textColor: "text-[var(--gray-11)]",
          iconColor: "text-[var(--gray-10)]",
        };
    }
  };

  const config = getStatusConfig();
  const showRetry = status === "disconnected" || status === "error";

  return (
    <div
      className={`border ${config.borderColor} ${config.bgColor} rounded-lg p-3 my-2`}
      data-block-type="connection-change"
      data-status={status}
    >
      <div className="flex items-start gap-3">
        <div className={`flex-shrink-0 ${config.iconColor}`}>{config.icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className={`text-sm font-medium ${config.textColor}`}>
              {config.title}
            </h4>
            {props.timestamp && (
              <span className="text-xs text-muted-foreground">
                {new Date(props.timestamp).toLocaleTimeString()}
              </span>
            )}
          </div>
          <div className={`text-sm ${config.textColor} opacity-90 mb-2`}>
            {config.message}
          </div>
          {showRetry && props.onRetry && (
            <Button
              size="xs"
              variant="outline"
              onClick={props.onRetry}
              className={`${config.textColor} ${config.borderColor} hover:${config.bgColor}`}
            >
              <RotateCcwIcon className="h-3 w-3 mr-1" />
              Retry Connection
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export const AgentThoughtsBlock = (props: {
  startTimestamp: number;
  endTimestamp: number;
  data: AgentThoughtNotificationEvent[];
}) => {
  const startAsSeconds = props.startTimestamp / 1000;
  const endAsSeconds = props.endTimestamp / 1000;
  const totalSeconds = Math.round(endAsSeconds - startAsSeconds) || "1";
  return (
    <div className="text-xs text-muted-foreground">
      <SimpleAccordion title={`Thought for ${totalSeconds}s`}>
        <div className="flex flex-col gap-2 text-muted-foreground">
          <ContentBlocks data={props.data.map((item) => item.content)} />
        </div>
      </SimpleAccordion>
    </div>
  );
};

export const PlansBlock = (props: { data: PlanNotificationEvent[] }) => {
  const plans = props.data.flatMap((item) => item.entries);

  return (
    <div className="rounded-lg border bg-background p-2 text-xs">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-muted-foreground">
          To-dos{" "}
          <span className="font-normal text-muted-foreground">
            {plans.length}
          </span>
        </span>
      </div>
      <ul className="flex flex-col gap-1">
        {plans.map((item, index) => (
          <li
            key={`${item.status}-${index}`}
            className={`
              flex items-center gap-2 px-2 py-1 rounded
            `}
          >
            <input
              type="checkbox"
              checked={item.status === "completed"}
              readOnly={true}
              className="accent-primary h-4 w-4 rounded border border-muted-foreground/30"
              tabIndex={-1}
            />
            <span
              className={cn(
                "text-xs",
                item.status === "completed" &&
                  "line-through text-muted-foreground",
              )}
            >
              {item.content}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export const UserMessagesBlock = (props: { data: UserNotificationEvent[] }) => {
  return (
    <div className="flex flex-col gap-2 text-muted-foreground border p-2 bg-background rounded break-words overflow-x-hidden">
      <ContentBlocks data={props.data.map((item) => item.content)} />
    </div>
  );
};

export const AgentMessagesBlock = (props: {
  data: AgentNotificationEvent[];
}) => {
  // Merge consecutive text chunks to prevent fragmented display
  const mergedContent = mergeConsecutiveTextBlocks(
    props.data.map((item) => item.content),
  );

  return (
    <div className="flex flex-col gap-2">
      <ContentBlocks data={mergedContent} />
    </div>
  );
};

export const ContentBlocks = (props: { data: ContentBlock[] }) => {
  const renderBlock = (block: ContentBlock) => {
    if (block.type === "text") {
      return <MarkdownRenderer content={block.text} />;
    }
    if (block.type === "image") {
      return <ImageBlock data={block} />;
    }
    if (block.type === "audio") {
      return <AudioBlock data={block} />;
    }
    if (block.type === "resource") {
      return <ResourceBlock data={block} />;
    }
    if (block.type === "resource_link") {
      return <ResourceLinkBlock data={block} />;
    }
    logNever(block);
    return null;
  };

  return (
    <div>
      {props.data.map((item, index) => {
        return (
          <React.Fragment key={`${item.type}-${index}`}>
            {renderBlock(item)}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export const ImageBlock = (props: { data: ContentBlockOf<"image"> }) => {
  return (
    <img
      src={`data:${props.data.mimeType};base64,${props.data.data}`}
      alt={props.data.uri ?? ""}
    />
  );
};

export const AudioBlock = (props: { data: ContentBlockOf<"audio"> }) => {
  return (
    <audio
      src={`data:${props.data.mimeType};base64,${props.data.data}`}
      controls={true}
    >
      <track kind="captions" />
    </audio>
  );
};

export const ResourceBlock = (props: { data: ContentBlockOf<"resource"> }) => {
  if ("text" in props.data.resource) {
    return (
      <Popover>
        <PopoverTrigger>
          <span className="flex items-center gap-1 hover:bg-muted rounded-md px-1">
            {props.data.resource.mimeType && (
              <MimeIcon mimeType={props.data.resource.mimeType} />
            )}
            {props.data.resource.uri}
          </span>
        </PopoverTrigger>
        <PopoverContent className="max-h-96 overflow-y-auto scrollbar-thin whitespace-pre-wrap w-full max-w-[500px]">
          <span className="text-muted-foreground text-xs mb-1 italic">
            Formatted for agents, not humans.
          </span>
          {props.data.resource.mimeType === "text/plain" ? (
            <pre className="text-xs whitespace-pre-wrap p-2 bg-muted rounded-md break-words">
              {props.data.resource.text}
            </pre>
          ) : (
            <MarkdownRenderer content={props.data.resource.text} />
          )}
        </PopoverContent>
      </Popover>
    );
  }
};

export const ResourceLinkBlock = (props: {
  data: ContentBlockOf<"resource_link">;
}) => {
  if (props.data.uri.startsWith("http")) {
    return (
      <a
        href={props.data.uri}
        target="_blank"
        rel="noopener noreferrer"
        className="text-link hover:underline px-1"
      >
        {props.data.name}
      </a>
    );
  }

  // Show image in popover for image mime types
  if (props.data.mimeType?.startsWith("image/")) {
    return (
      <div>
        <Popover>
          <PopoverTrigger>
            <span className="flex items-center gap-1 hover:bg-muted rounded-md px-1 cursor-pointer">
              <MimeIcon mimeType={props.data.mimeType} />
              {props.data.name || props.data.title || props.data.uri}
            </span>
          </PopoverTrigger>
          <PopoverContent className="w-auto max-w-[500px] p-2">
            <img
              src={props.data.uri}
              alt={props.data.name || props.data.title || "Image"}
              className="max-w-full max-h-96 object-contain"
            />
          </PopoverContent>
        </Popover>
      </div>
    );
  }

  return (
    <span className="flex items-center gap-1 px-1">
      {props.data.mimeType && <MimeIcon mimeType={props.data.mimeType} />}
      {props.data.name || props.data.title || props.data.uri}
    </span>
  );
};

export const MimeIcon = (props: { mimeType: string }) => {
  const classNames = "h-2 w-2 flex-shrink-0";
  if (props.mimeType.startsWith("image/")) {
    return <FileImageIcon className={classNames} />;
  }
  if (props.mimeType.startsWith("audio/")) {
    return <FileAudio2Icon className={classNames} />;
  }
  if (props.mimeType.startsWith("video/")) {
    return <FileVideoCameraIcon className={classNames} />;
  }
  if (props.mimeType.startsWith("text/")) {
    return <FileTextIcon className={classNames} />;
  }
  if (props.mimeType.startsWith("application/")) {
    return <FileJsonIcon className={classNames} />;
  }
  return <FileIcon className={classNames} />;
};

export const SessionNotificationsBlock = <
  T extends SessionNotificationEventData,
>(props: {
  data: T[];
  startTimestamp: number;
  endTimestamp: number;
}) => {
  if (props.data.length === 0) {
    return null;
  }
  const kind = props.data[0].sessionUpdate;

  const renderItems = (items: T[]) => {
    if (isToolCalls(items)) {
      return <ToolNotificationsBlock data={items} />;
    }
    if (isAgentThoughts(items)) {
      return (
        <AgentThoughtsBlock
          startTimestamp={props.startTimestamp}
          endTimestamp={props.endTimestamp}
          data={items}
        />
      );
    }
    if (isUserMessages(items)) {
      return <UserMessagesBlock data={items} />;
    }
    if (isAgentMessages(items)) {
      return <AgentMessagesBlock data={items} />;
    }
    if (isPlans(items)) {
      return <PlansBlock data={items} />;
    }

    if (kind === "available_commands_update") {
      return null; // nothing to show
    }
    if (kind === "current_mode_update") {
      const lastItem = items.at(-1);
      return lastItem?.sessionUpdate === "current_mode_update" ? (
        <CurrentModeBlock data={lastItem} />
      ) : null;
    }

    return (
      <SimpleAccordion title={items[0].sessionUpdate}>
        <JsonOutput data={items} format="tree" className="max-h-64" />
      </SimpleAccordion>
    );
  };

  return (
    <div className="flex flex-col text-sm gap-2" data-block-type={kind}>
      {renderItems(props.data)}
    </div>
  );
};

export const CurrentModeBlock = (props: {
  data: CurrentModeUpdateNotificationEvent;
}) => {
  const { currentModeId } = props.data;
  return <div>Mode: {currentModeId}</div>;
};

export const ToolNotificationsBlock = (props: {
  data: (ToolCallNotificationEvent | ToolCallUpdateNotificationEvent)[];
}) => {
  const toolCalls = mergeToolCalls(props.data);

  return (
    <div className="flex flex-col text-muted-foreground overflow-x-hidden">
      {toolCalls.map((item) => (
        <SimpleAccordion
          key={item.toolCallId}
          status={
            item.status === "completed"
              ? "success"
              : item.status === "failed"
                ? "error"
                : item.status === "in_progress" || item.status === "pending"
                  ? "loading"
                  : undefined
          }
          title={
            <span data-tool-data={JSON.stringify(item)}>
              {handleBackticks(toolTitle(item))}
            </span>
          }
          defaultIcon={<WrenchIcon className="h-3 w-3" />}
        >
          <ToolBodyBlock data={item} />
        </SimpleAccordion>
      ))}
    </div>
  );
};

export const DiffBlocks = (props: {
  data: Extract<ToolCallContent, { type: "diff" }>[];
}) => {
  return (
    <div className="flex flex-col gap-2 text-muted-foreground">
      {props.data.map((item) => {
        return (
          <div
            key={item.path}
            className="border rounded-md overflow-hidden bg-[var(--gray-2)] overflow-y-auto scrollbar-thin"
          >
            {/* File path header */}
            <div className="px-2 py-1 bg-[var(--gray-2)] border-b text-xs font-medium text-[var(--gray-11)]">
              {item.path}
            </div>
            <ReadonlyDiff
              original={item.oldText || ""}
              modified={item.newText || ""}
            />
          </div>
        );
      })}
    </div>
  );
};

function toolTitle(
  item: Pick<ToolCallUpdateNotificationEvent, "title" | "kind" | "locations">,
) {
  const prefix =
    item.title || Strings.startCase(item.kind || "") || "Tool call";
  const firstLocation = item.locations?.[0];
  // Add the first location if it is not in the title already
  if (firstLocation && !prefix.includes(firstLocation.path)) {
    return `${prefix}: ${firstLocation.path}`;
  }
  return prefix;
}

function handleBackticks(text: string) {
  if (text.startsWith("`") && text.endsWith("`")) {
    return <i>{text.slice(1, -1)}</i>;
  }
  return text;
}

export const LocationsBlock = (props: { data: ToolCallLocation[] }) => {
  // Only show locations if there are multiple locations, otherwise it is
  // in the title
  if (props.data.length <= 1) {
    return null;
  }

  const locations = props.data.map((item) => {
    if (item.line) {
      return `${item.path}:${item.line}`;
    }
    return item.path;
  });
  return <div className="flex flex-col gap-2">{locations.join("\n")}</div>;
};

export const ToolBodyBlock = (props: {
  data:
    | Omit<ToolCallNotificationEvent, "sessionUpdate">
    | Omit<ToolCallUpdateNotificationEvent, "sessionUpdate">;
}) => {
  const { content, locations, status, kind, rawInput } = props.data;
  const textContent = content
    ?.filter((item) => item.type === "content")
    .map((item) => item.content);
  const diffs = content?.filter((item) => item.type === "diff");
  const isFailed = status === "failed";
  const hasLocations = locations && locations.length > 0;

  // Completely empty
  if (!content && !hasLocations && rawInput) {
    // Show rawInput
    return (
      <pre className="bg-[var(--slate-2)] p-1 text-muted-foreground border border-[var(--slate-4)] rounded text-xs overflow-auto scrollbar-thin max-h-64">
        <JsonOutput data={rawInput} format="tree" />
      </pre>
    );
  }

  const noContent = !textContent || textContent.length === 0;
  const noDiffs = !diffs || diffs.length === 0;
  if (noContent && noDiffs && hasLocations) {
    return (
      <div className="flex flex-col gap-2 pr-2">
        <span className="text-xs text-muted-foreground">
          {capitalize(kind || "")}{" "}
          {locations?.map((item) => item.path).join(", ")}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 pr-2">
      {locations && <LocationsBlock data={locations} />}
      {textContent && <ContentBlocks data={textContent} />}
      {diffs && !isFailed && <DiffBlocks data={diffs} />}
    </div>
  );
};
