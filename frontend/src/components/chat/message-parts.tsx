/* Copyright 2024 Marimo. All rights reserved. */

import type { ToolUIPart, UIMessage } from "ai";
import React from "react";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";
import { Logger } from "@/utils/Logger";
import { ReasoningAccordion } from "./reasoning-accordion";
import { ToolCallAccordion } from "./tool-call-accordion";

// Type guards for different part types
export function isToolPart(
  part: UIMessage["parts"][number],
): part is ToolUIPart {
  return part.type.startsWith("tool-");
}

export function isReasoningPart(
  part: UIMessage["parts"][number],
): part is { type: "reasoning"; text: string } {
  return part.type === "reasoning";
}

export interface MessagePartsProps {
  parts: UIMessage["parts"];
  isStreaming?: boolean;
  className?: string;
}

/**
 * Renders message parts (reasoning, tools, text, etc.) in a consistent way.
 * Used by both the chat UI widget and the chat panel/sidebar.
 */
export const MessageParts: React.FC<MessagePartsProps> = ({
  parts,
  isStreaming = false,
  className,
}) => {
  const reasoningParts = parts.filter(isReasoningPart);
  const toolParts = parts.filter(isToolPart);
  const contentParts = parts.filter(
    (p) => !isToolPart(p) && !isReasoningPart(p),
  );

  return (
    <div className={className}>
      {/* Reasoning parts */}
      {reasoningParts.length > 0 && (
        <div className="space-y-2 mb-2">
          {reasoningParts.map((part, index) => (
            <ReasoningAccordion
              key={`reasoning-${index}`}
              reasoning={part.text}
              index={index}
              isStreaming={isStreaming}
            />
          ))}
        </div>
      )}

      {/* Tool call parts */}
      {toolParts.length > 0 && (
        <div className="space-y-2 mb-2">
          {toolParts.map((part, index) => (
            <ToolCallAccordion
              key={`tool-${index}`}
              index={index}
              toolName={part.type}
              result={part.output}
              state={part.state}
              input={part.input}
            />
          ))}
        </div>
      )}

      {/* Content parts (text, files, etc.) */}
      {contentParts.map((part, index) => {
        switch (part.type) {
          case "text":
            return part.text ? (
              <MarkdownRenderer key={`text-${index}`} content={part.text} />
            ) : null;

          case "dynamic-tool":
            return (
              <ToolCallAccordion
                key={`dynamic-tool-${index}`}
                index={index}
                toolName={part.type}
                result={part.output}
                state={part.state}
                input={part.input}
                className="my-2"
              />
            );

          // Cryptographic signatures - don't render
          case "data-reasoning-signature":
            return null;

          default:
            // Skip data-* parts silently
            if (part.type.startsWith("data-")) {
              return null;
            }

            // Log unhandled types for debugging
            Logger.error("Unhandled part type:", part.type);
            try {
              return (
                <div
                  className="text-xs text-muted-foreground my-1"
                  key={`unknown-${index}`}
                >
                  <MarkdownRenderer content={JSON.stringify(part, null, 2)} />
                </div>
              );
            } catch {
              return null;
            }
        }
      })}
    </div>
  );
};
