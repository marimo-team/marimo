/* Copyright 2024 Marimo. All rights reserved. */
import type {
  ContentBlock,
  ToolCallContent,
  ToolCallLocation,
} from "@zed-industries/agent-client-protocol";
import { capitalize } from "lodash-es";
import {
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
import { Streamdown } from "streamdown";
import { mergeToolCalls } from "use-acp";
import { JsonOutput } from "@/components/editor/output/JsonOutput";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import { Strings } from "@/utils/strings";
import { SimpleAccordion } from "./common";
import type {
  AgentNotificationEvent,
  AgentThoughtNotificationEvent,
  ConnectionChangeNotificationEvent,
  ContentBlockOf,
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

export const ErrorBlock = (props: {
  data: ErrorNotificationEvent["data"];
  onRetry?: () => void;
  onDismiss?: () => void;
}) => {
  const { message } = props.data;

  // Don't show WebSocket connection errors
  if (message.includes("WebSocket")) {
    return null;
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

export const ConnectionChangeBlock = (props: {
  data: ConnectionChangeNotificationEvent["data"];
  isConnected: boolean;
  onRetry?: () => void;
  timestamp?: number;
}) => {
  const { status } = props.data;

  if (props.isConnected) {
    return null;
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
    <div className="flex flex-col gap-2 text-muted-foreground border p-2 bg-background rounded break-words">
      <ContentBlocks data={props.data.map((item) => item.content)} />
    </div>
  );
};

export const AgentMessagesBlock = (props: {
  data: AgentNotificationEvent[];
}) => {
  return (
    <div className="flex flex-col gap-2">
      <ContentBlocks data={props.data.map((item) => item.content)} />
    </div>
  );
};

export const ContentBlocks = (props: { data: ContentBlock[] }) => {
  const renderBlock = (block: ContentBlock) => {
    if (block.type === "text") {
      return <Streamdown>{block.text}</Streamdown>;
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
          <span className="flex items-center gap-1">
            {props.data.resource.mimeType && (
              <MimeIcon mimeType={props.data.resource.mimeType} />
            )}
            {props.data.resource.uri}
          </span>
        </PopoverTrigger>
        <PopoverContent className="max-h-96 overflow-y-auto scrollbar-thin">
          <Streamdown>{props.data.resource.text}</Streamdown>
        </PopoverContent>
      </Popover>
    );
  }

  if ("blob" in props.data.resource) {
    if (props.data.resource.mimeType?.startsWith("image/")) {
      return (
        <ImageBlock
          data={{
            type: "image",
            mimeType: props.data.resource.mimeType,
            data: props.data.resource.blob,
          }}
        />
      );
    }
    if (props.data.resource.mimeType?.startsWith("audio/")) {
      return (
        <AudioBlock
          data={{
            type: "audio",
            mimeType: props.data.resource.mimeType,
            data: props.data.resource.blob,
          }}
        />
      );
    }
    const dataURL = base64ToDataURL(
      props.data.resource.blob as Base64String,
      props.data.resource.mimeType ?? "",
    );
    return (
      <a href={dataURL} className="flex items-center gap-1" download={true}>
        {props.data.resource.mimeType && (
          <MimeIcon mimeType={props.data.resource.mimeType} />
        )}
        {props.data.resource.uri}
      </a>
    );
  }
  logNever(props.data.resource);
  return null;
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
        className="text-link hover:underline"
      >
        {props.data.name}
      </a>
    );
  }

  return (
    <span className="flex items-center gap-1">
      {props.data.mimeType && <MimeIcon mimeType={props.data.mimeType} />}
      {props.data.name || props.data.title || props.data.uri}
    </span>
  );
};

export const MimeIcon = (props: { mimeType: string }) => {
  if (props.mimeType.startsWith("image/")) {
    return <FileImageIcon className="h-2 w-2" />;
  }
  if (props.mimeType.startsWith("audio/")) {
    return <FileAudio2Icon className="h-2 w-2" />;
  }
  if (props.mimeType.startsWith("video/")) {
    return <FileVideoCameraIcon className="h-2 w-2" />;
  }
  if (props.mimeType.startsWith("text/")) {
    return <FileTextIcon className="h-2 w-2" />;
  }
  if (props.mimeType.startsWith("application/")) {
    return <FileJsonIcon className="h-2 w-2" />;
  }
  return <FileIcon className="h-2 w-2" />;
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

export const ToolNotificationsBlock = (props: {
  data: Array<ToolCallNotificationEvent | ToolCallUpdateNotificationEvent>;
}) => {
  const toolCalls = mergeToolCalls(props.data);

  return (
    <div className="flex flex-col text-muted-foreground">
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
  data: Array<Extract<ToolCallContent, { type: "diff" }>>;
}) => {
  return (
    <div className="flex flex-col gap-2 text-muted-foreground">
      {props.data.map((item) => {
        return (
          <div
            key={item.path}
            className="border rounded-md overflow-hidden bg-[var(--gray-2)] max-h-64 overflow-y-auto scrollbar-thin"
          >
            {/* File path header */}
            <div className="px-2 py-1 bg-[var(--gray-2)] border-b text-xs font-medium text-[var(--gray-11)]">
              {item.path}
            </div>

            <div className="font-mono text-xs">
              {/* Removed lines */}
              {item.oldText && (
                <div className="px-3 py-1 border-b bg-[var(--red-2)] border-b-[var(--red-6)]">
                  <div className="flex">
                    <span className="text-[var(--red-11)] select-none mr-2">
                      -
                    </span>
                    <pre className="text-[var(--red-11)] px-1 rounded whitespace-pre-wrap break-words flex-1 line-through opacity-80">
                      {item.oldText}
                    </pre>
                  </div>
                </div>
              )}

              {/* Added lines */}
              {item.newText && (
                <div className="px-3 py-1 bg-[var(--grass-2)] border-b-[var(--grass-6)]">
                  <div className="flex">
                    <span className="text-[var(--grass-11)] select-none mr-2">
                      +
                    </span>
                    <pre className="text-[var(--grass-11)] px-1 rounded whitespace-pre-wrap break-words flex-1 italic opacity-90">
                      {item.newText}
                    </pre>
                  </div>
                </div>
              )}
            </div>
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
  const content = props.data.content
    ?.filter((item) => item.type === "content")
    .map((item) => item.content);
  const diffs = props.data.content?.filter((item) => item.type === "diff");
  const locations = props.data.locations;
  const isFailed = props.data.status === "failed";
  const hasLocations = locations && locations.length > 0;

  if (content?.length === 0 && diffs?.length === 0 && hasLocations) {
    return (
      <div className="flex flex-col gap-2 pr-2">
        <span className="text-xs text-muted-foreground">
          {capitalize(props.data.kind || "")}{" "}
          {locations?.map((item) => item.path).join(", ")}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 pr-2">
      {locations && <LocationsBlock data={locations} />}
      {content && <ContentBlocks data={content} />}
      {diffs && !isFailed && <DiffBlocks data={diffs} />}
    </div>
  );
};
