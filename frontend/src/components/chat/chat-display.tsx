/* Copyright 2026 Marimo. All rights reserved. */

import type {
  ChatAddToolApproveResponseFunction,
  DataUIPart,
  DynamicToolUIPart,
  ToolUIPart,
  UIMessage,
} from "ai";
import { ExternalLinkIcon, FileTextIcon } from "lucide-react";
import React from "react";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { logNever } from "@/utils/assertNever";
import { AgentActivity } from "./agent-activity";
import { AttachmentRenderer, SourceChip } from "./chat-components";
import { ChatMarkdown } from "./chat-markdown";
import { PENDING_TOOL_STATES } from "./tool-call/shared";
import { ToolCallView } from "./tool-call/tool-call-view";
import { getTurnTiming } from "./turn-timing";

type Part = UIMessage["parts"][number];
interface IndexedPart {
  part: Part;
  index: number;
}

export const renderUIMessage = ({
  message,
  isLast,
  isActive,
  turnStartedAt,
  addToolApprovalResponse,
}: {
  message: UIMessage;
  isLast: boolean;
  /** Whether the chat is currently streaming/submitting a response. */
  isActive: boolean;
  turnStartedAt?: number | null;
  addToolApprovalResponse?: ChatAddToolApproveResponseFunction;
}): React.ReactNode[] => {
  const running = isActive && isLast;
  const { work, rest } = splitTurn(message.parts);
  const content: React.ReactNode[] = [];

  if (work.length > 0 || (running && rest.length === 0)) {
    const tools = work.flatMap(({ part }) =>
      isAnyToolPart(part) ? [part] : [],
    );
    const timing =
      running && turnStartedAt != null
        ? { startedAt: turnStartedAt }
        : getTurnTiming(message);
    content.push(
      <AgentActivity
        key="activity"
        running={running}
        thinking={
          rest.length === 0 &&
          (work.length === 0 || work.at(-1)?.part.type === "reasoning")
        }
        interrupted={
          !running &&
          (timing?.stopped === true ||
            tools.some((part) => PENDING_TOOL_STATES.has(part.state)))
        }
        defaultOpen={!rest.some(({ part }) => !isPendingApproval(part))}
        timing={timing}
        toolCount={tools.length}
        failedCount={
          tools.filter((part) => part.state === "output-error").length
        }
        steps={work.map(({ part, index }) => renderPart(part, index, true))}
      />,
    );
  }
  for (const { part, index } of rest) {
    content.push(renderPart(part, index, false));
  }
  return content;

  function renderPart(part: Part, index: number, inActivity: boolean) {
    if (isToolPart(part) || part.type === "dynamic-tool") {
      return (
        <ToolCallView
          key={index}
          toolName={part.type === "dynamic-tool" ? part.toolName : part.type}
          result={part.output}
          errorText={part.state === "output-error" ? part.errorText : undefined}
          state={part.state}
          input={part.input}
          approval={part.approval}
          onApprove={addToolApprovalResponse}
          isActive={running}
          className={inActivity ? undefined : "my-1"}
        />
      );
    }
    if (isDataPart(part)) {
      return null;
    }

    switch (part.type) {
      case "text":
        // Streamdown strips marimo elements, so render them with our own HTML
        // renderer. Other markdown (incl. mo.md HTML) goes through Streamdown.
        if (part.text.includes("<marimo-")) {
          return (
            <React.Fragment key={index}>
              {renderHTML({ html: part.text })}
            </React.Fragment>
          );
        }
        return (
          <div key={index} className={inActivity ? "py-1.5" : undefined}>
            <ChatMarkdown content={part.text} />
          </div>
        );
      case "reasoning":
        return (
          <div key={index} className="py-1.5 text-muted-foreground [&_p]:my-1">
            <ChatMarkdown content={part.text} />
          </div>
        );
      case "file":
        return <AttachmentRenderer attachment={part} key={index} />;
      case "reasoning-file":
        return (
          <AttachmentRenderer
            key={index}
            attachment={{
              type: "file",
              mediaType: part.mediaType,
              url: part.url,
            }}
          />
        );
      case "source-document":
        return (
          <SourceChip
            key={index}
            icon={<FileTextIcon className="h-3 w-3 shrink-0" />}
            title={part.title}
            subtitle={part.filename}
          />
        );
      case "source-url":
        return (
          <SourceChip
            key={index}
            icon={<ExternalLinkIcon className="h-3 w-3 shrink-0" />}
            title={part.title ?? part.url}
            subtitle={part.title ? part.url : undefined}
            href={part.url}
          />
        );
      case "custom":
        return (
          <div key={index} className="text-sm text-muted-foreground">
            {part.kind}
          </div>
        );
      case "step-start":
        return null;
      default:
        logNever(part);
        return null;
    }
  }
};

export function getAnswerText(message: UIMessage): string {
  const textOf = (parts: IndexedPart[]) =>
    parts.flatMap(({ part }) => (part.type === "text" ? [part.text] : []));
  const { work, rest } = splitTurn(message.parts);
  const answer = textOf(rest);
  return (answer.length > 0 ? answer : textOf(work)).join("\n");
}

function splitTurn(parts: UIMessage["parts"]): {
  work: IndexedPart[];
  rest: IndexedPart[];
} {
  const visible = parts
    .map((part, index) => ({ part, index }))
    .filter(({ part }) => isVisible(part));
  const lastWork = visible.findLastIndex(
    ({ part }) =>
      part.type === "reasoning" ||
      (isAnyToolPart(part) && !isPendingApproval(part)),
  );
  return {
    work: visible.filter(
      ({ part }, i) => i <= lastWork && !isPendingApproval(part),
    ),
    rest: visible.filter(
      ({ part }, i) => i > lastWork || isPendingApproval(part),
    ),
  };
}

function isPendingApproval(part: Part): boolean {
  return isAnyToolPart(part) && part.state === "approval-requested";
}

function isVisible(part: Part): boolean {
  switch (part.type) {
    case "step-start":
      return false;
    case "text":
      return part.text.trim().length > 0;
    case "reasoning":
      // Some models (e.g. OpenAI's o-series) emit empty reasoning parts.
      return part.text.trim().length > 0;
    default:
      return !isDataPart(part);
  }
}

function isAnyToolPart(part: Part): part is ToolUIPart | DynamicToolUIPart {
  return isToolPart(part) || part.type === "dynamic-tool";
}

function isToolPart(part: Part): part is ToolUIPart {
  return part.type.startsWith("tool-");
}

function isDataPart(part: Part): part is DataUIPart<Record<string, unknown>> {
  return part.type.startsWith("data-");
}
