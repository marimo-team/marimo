/* Copyright 2026 Marimo. All rights reserved. */

import type { DataUIPart, ToolUIPart, UIMessage } from "ai";
import { logNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";
import { MarkdownRenderer } from "../markdown/markdown-renderer";
import { AttachmentRenderer } from "./chat-components";
import { ReasoningAccordion } from "./reasoning-accordion";
import { ToolCallAccordion } from "./tool-call-accordion";

export const renderUIMessage = ({
  message,
  isStreamingReasoning,
  isLast,
}: {
  message: UIMessage;
  isStreamingReasoning: boolean;
  isLast: boolean;
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
        <ToolCallAccordion
          key={index}
          index={index}
          toolName={part.type}
          result={part.output}
          className="my-2"
          state={part.state}
          input={part.input}
        />
      );
    }

    if (isDataPart(part)) {
      Logger.debug("Found data part", part);
      return null;
    }

    switch (part.type) {
      case "text":
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
              // If there are multiple reasoning parts, only show the last one
              index === (message.parts.length || 0) - 1
            }
          />
        );
      case "file":
        return <AttachmentRenderer attachment={part} key={index} />;
      case "dynamic-tool":
        return (
          <ToolCallAccordion
            key={index}
            toolName={part.toolName}
            result={part.output}
            state={part.state}
            input={part.input}
          />
        );
      case "source-document":
      case "source-url":
      case "step-start":
        Logger.debug("Found non-renderable part", part);
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
