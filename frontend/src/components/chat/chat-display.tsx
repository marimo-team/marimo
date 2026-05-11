/* Copyright 2026 Marimo. All rights reserved. */

import type {
  ChatAddToolApproveResponseFunction,
  DataUIPart,
  ToolUIPart,
  UIMessage,
} from "ai";
import { ExternalLinkIcon, FileTextIcon } from "lucide-react";
import React from "react";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";
import { MarkdownRenderer } from "../markdown/markdown-renderer";
import { AttachmentRenderer, SourceChip } from "./chat-components";
import { ReasoningAccordion } from "./reasoning-accordion";
import { ToolCallView } from "./tool-call/tool-call-view";

export const renderUIMessage = ({
  message,
  isStreamingReasoning,
  isLast,
  addToolApprovalResponse,
}: {
  message: UIMessage;
  isStreamingReasoning: boolean;
  isLast: boolean;
  addToolApprovalResponse?: ChatAddToolApproveResponseFunction;
}) => {
  return (
    <>{message.parts.map((part, index) => renderUIMessagePart(part, index))}</>
  );

  function renderUIMessagePart(
    part: UIMessage["parts"][number],
    index: number,
  ) {
    if (isToolPart(part)) {
      return (
        <ToolCallView
          key={index}
          index={index}
          toolName={part.type}
          result={part.output}
          errorText={part.state === "output-error" ? part.errorText : undefined}
          className="my-2"
          state={part.state}
          input={part.input}
          approval={part.approval}
          onApprove={addToolApprovalResponse}
          isLive={isLast}
        />
      );
    }

    if (isDataPart(part)) {
      Logger.debug("Found data part", part);
      return null;
    }

    switch (part.type) {
      case "text":
        // Streamdown sanitizes the HTML which strips out marimo elements
        // So instead, we render the HTML with our custom renderer.
        if (part.text.includes("<marimo-")) {
          return (
            <React.Fragment key={index}>
              {renderHTML({
                html: part.text,
              })}
            </React.Fragment>
          );
        }
        return <MarkdownRenderer key={index} content={part.text} />;
      case "reasoning":
        return (
          <ReasoningAccordion
            key={index}
            reasoning={part.text}
            index={index}
            isStreaming={
              isStreamingReasoning &&
              isLast &&
              // If there are multiple reasoning parts, only stream the last one
              index === (message.parts.length || 0) - 1
            }
          />
        );
      case "file":
        return <AttachmentRenderer attachment={part} key={index} />;
      case "dynamic-tool":
        return (
          <ToolCallView
            key={index}
            toolName={part.toolName}
            result={part.output}
            errorText={
              part.state === "output-error" ? part.errorText : undefined
            }
            state={part.state}
            input={part.input}
            approval={part.approval}
            onApprove={addToolApprovalResponse}
            isLive={isLast}
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
      case "step-start":
        return null;
      default:
        logNever(part);
        return null;
    }
  }
};

function isToolPart(part: UIMessage["parts"][number]): part is ToolUIPart {
  return part.type.startsWith("tool-");
}

function isDataPart(
  part: UIMessage["parts"][number],
): part is DataUIPart<Record<string, unknown>> {
  return part.type.startsWith("data-");
}
