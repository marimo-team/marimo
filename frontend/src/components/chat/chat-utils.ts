/* Copyright 2024 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import type { FileUIPart, ToolUIPart, UIMessage } from "ai";
import { FRONTEND_TOOL_REGISTRY } from "@/core/ai/tools/registry";
import type {
  InvokeAiToolRequest,
  InvokeAiToolResponse,
} from "@/core/network/types";
import type { ChatMessage } from "@/plugins/impl/chat/types";
import { blobToString } from "@/utils/fileToBase64";
import { Logger } from "@/utils/Logger";
import { getAICompletionBodyWithAttachments } from "../editor/ai/completion-utils";

export function generateChatTitle(message: string): string {
  return message.length > 50 ? `${message.slice(0, 50)}...` : message;
}

export async function convertToFileUIPart(
  files: File[],
): Promise<FileUIPart[]> {
  const fileUIParts = await Promise.all(
    files.map(async (file) => {
      const part: FileUIPart = {
        type: "file" as const,
        mediaType: file.type,
        filename: file.name,
        url: await blobToString(file, "dataUrl"),
      };
      return part;
    }),
  );

  return fileUIParts;
}

export function isLastMessageReasoning(messages: UIMessage[]): boolean {
  if (messages.length === 0) {
    return false;
  }

  const lastMessage = messages.at(-1);
  if (!lastMessage) {
    return false;
  }

  if (lastMessage.role !== "assistant" || !lastMessage.parts) {
    return false;
  }

  const parts = lastMessage.parts;
  if (parts.length === 0) {
    return false;
  }

  // Check if the last part is reasoning
  const lastPart = parts[parts.length - 1];
  return lastPart.type === "reasoning";
}

function stringifyTextParts(parts: UIMessage["parts"]): string {
  return parts
    .map((part) => (part.type === "text" ? part.text : ""))
    .join("\n");
}

export async function buildCompletionRequestBody(
  messages: UIMessage[],
): Promise<{
  messages: ChatMessage[];
  context?: (null | components["schemas"]["AiCompletionContext"]) | undefined;
  includeOtherCode: string;
  selectedText?: string | null | undefined;
}> {
  const input = stringifyTextParts(messages.flatMap((m) => m.parts));
  const completionBody = await getAICompletionBodyWithAttachments({ input });

  // Map from UIMessage to our ChatMessage type
  // If it's the last message, add the attachments from the completion body
  function toChatMessage(message: UIMessage, isLast: boolean): ChatMessage {
    // Clone parts to avoid mutating the original message
    const parts = [...message.parts];
    if (isLast) {
      parts.push(...completionBody.attachments);
    }
    return {
      role: message.role,
      content: stringifyTextParts(message.parts), // This is no longer used in the backend
      parts,
    };
  }

  return {
    ...completionBody.body,
    messages: messages.map((m, idx) =>
      toChatMessage(m, idx === messages.length - 1),
    ),
  };
}

interface AddToolResult {
  tool: string;
  toolCallId: string;
  output: unknown;
}

export async function handleToolCall({
  invokeAiTool,
  addToolResult,
  toolCall,
}: {
  invokeAiTool: (request: InvokeAiToolRequest) => Promise<InvokeAiToolResponse>;
  addToolResult: (result: AddToolResult) => Promise<void>;
  toolCall: {
    toolName: string;
    toolCallId: string;
    input: Record<string, never>;
  };
}) {
  try {
    if (FRONTEND_TOOL_REGISTRY.has(toolCall.toolName)) {
      // Invoke the frontend tool
      const response = await FRONTEND_TOOL_REGISTRY.invoke(
        toolCall.toolName,
        toolCall.input,
      );
      addToolResult({
        tool: toolCall.toolName,
        toolCallId: toolCall.toolCallId,
        output: response.result || response.error,
      });
    } else {
      // Invoke the backend/mcp tool
      const response = await invokeAiTool({
        toolName: toolCall.toolName,
        arguments: toolCall.input,
      });
      addToolResult({
        tool: toolCall.toolName,
        toolCallId: toolCall.toolCallId,
        output: response.result || response.error,
      });
    }
  } catch (error) {
    Logger.error("Tool call failed:", error);
    addToolResult({
      tool: toolCall.toolName,
      toolCallId: toolCall.toolCallId,
      output: `Error: ${error instanceof Error ? error.message : String(error)}`,
    });
  }
}

/**
 * Checks if we should send a message automatically based on the messages.
 * We only want to send a message if all tool calls are completed and there is no reply yet.
 */
export function hasPendingToolCalls(messages: UIMessage[]): boolean {
  if (messages.length === 0) {
    return false;
  }

  const lastMessage = messages[messages.length - 1];
  const parts = lastMessage.parts;

  if (parts.length === 0) {
    return false;
  }

  // Only auto-send if the last message is an assistant message
  // Because assistant messages are the ones that can have tool calls
  if (lastMessage.role !== "assistant") {
    return false;
  }

  const toolParts = parts.filter((part) =>
    part.type.startsWith("tool-"),
  ) as ToolUIPart[];

  // Guard against no tool parts
  if (toolParts.length === 0) {
    return false;
  }

  const allToolCallsCompleted = toolParts.every(
    (part) => part.state === "output-available",
  );

  // Check if the last part has any text content
  const lastPart = parts[parts.length - 1];
  const hasTextContent =
    lastPart.type === "text" && lastPart.text?.trim().length > 0;

  Logger.warn("All tool calls completed: %s", allToolCallsCompleted);

  // Only auto-send if we have completed tool calls and there is no reply yet
  return allToolCallsCompleted && !hasTextContent;
}
