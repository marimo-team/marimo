/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import {
  type ChatAddToolOutputFunction,
  type FileUIPart,
  isToolUIPart,
  type ToolUIPart,
  type UIMessage,
} from "ai";
import { useState } from "react";
import useEvent from "react-use-event-hook";
import type { ProviderId } from "@/core/ai/ids/ids";
import type { ToolNotebookContext } from "@/core/ai/tools/base";
import { FRONTEND_TOOL_REGISTRY } from "@/core/ai/tools/registry";
import type {
  InvokeAiToolRequest,
  InvokeAiToolResponse,
} from "@/core/network/types";
import { logNever } from "@/utils/assertNever";
import { blobToString } from "@/utils/fileToBase64";
import { Logger } from "@/utils/Logger";
import { getAICompletionBodyWithAttachments } from "../editor/ai/completion-utils";
import { toast } from "../ui/use-toast";

// We need to modify the backend to support attachments for other providers
// And other types
export const PROVIDERS_THAT_SUPPORT_ATTACHMENTS = new Set<ProviderId>([
  "openai",
  "google",
  "anthropic",
]);
export const SUPPORTED_ATTACHMENT_TYPES = ["image/*", "text/*"];
const MAX_ATTACHMENT_SIZE = 1024 * 1024 * 50; // 50MB

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
  uiMessages: UIMessage[];
  context?: (null | components["schemas"]["AiCompletionContext"]) | undefined;
  includeOtherCode: string;
  selectedText?: string | null | undefined;
}> {
  const input = stringifyTextParts(messages.flatMap((m) => m.parts));
  const completionBody = await getAICompletionBodyWithAttachments({ input });

  // If it's the last message, add the attachments from the completion body
  function addAttachmentsToMessage(
    message: UIMessage,
    isLast: boolean,
  ): UIMessage {
    if (!isLast) {
      return message;
    }
    return {
      ...message,
      parts: [...message.parts, ...completionBody.attachments],
    };
  }

  return {
    ...completionBody.body,
    uiMessages: messages.map((m, idx) =>
      addAttachmentsToMessage(m, idx === messages.length - 1),
    ),
  };
}

export async function handleToolCall({
  invokeAiTool,
  addToolOutput, // Important that we don't await addToolOutput to prevent potential deadlocks
  toolCall,
  toolContext,
}: {
  invokeAiTool: (request: InvokeAiToolRequest) => Promise<InvokeAiToolResponse>;
  addToolOutput: ChatAddToolOutputFunction<UIMessage>;
  toolCall: {
    toolName: string;
    toolCallId: string;
    input: Record<string, never>;
  };
  toolContext: ToolNotebookContext;
}) {
  try {
    if (FRONTEND_TOOL_REGISTRY.has(toolCall.toolName)) {
      // Invoke the frontend tool
      const response = await FRONTEND_TOOL_REGISTRY.invoke({
        toolName: toolCall.toolName,
        rawArgs: toolCall.input,
        toolContext: toolContext,
      });
      addToolOutput({
        tool: toolCall.toolName,
        toolCallId: toolCall.toolCallId,
        output: response.result || response.error,
      });
    } else {
      // Invoke the backend/mcp tool
      const response = await invokeAiTool({
        toolName: toolCall.toolName,
        arguments: toolCall.input ?? {}, // Some models pass in null, so we default to an empty object
      });
      addToolOutput({
        tool: toolCall.toolName,
        toolCallId: toolCall.toolCallId,
        output: response.result || response.error,
      });
    }
  } catch (error) {
    Logger.error("Tool call failed:", error);
    addToolOutput({
      tool: toolCall.toolName,
      toolCallId: toolCall.toolCallId,
      output: `Error: ${error instanceof Error ? error.message : String(error)}`,
    });
  }
}

/**
 * Returns true if a tool call is "ready to be sent back to the server" — i.e.
 * either it has reached a terminal output state, or the user has just supplied
 * an approval response that the server hasn't seen yet.
 */
function isToolCallReadyToSend(state: ToolUIPart["state"]): boolean {
  switch (state) {
    case "output-available":
    case "output-error":
    case "output-denied":
    case "approval-responded":
      return true;
    case "input-streaming":
    case "input-available":
    case "approval-requested":
      return false;
    default:
      logNever(state);
      return false;
  }
}

/**
 * Checks if we should send a message automatically based on the messages.
 * We auto-send when every tool call on the last assistant message has either
 * finished (output-available/error/denied) or has just received a user
 * approval response, and the assistant hasn't replied yet.
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

  const toolParts = parts.filter(isToolUIPart);

  if (toolParts.length === 0) {
    return false;
  }

  const allToolCallsReady = toolParts.every((part) =>
    isToolCallReadyToSend(part.state),
  );

  // Check if the last part has any text content
  const lastPart = parts[parts.length - 1];
  const hasTextContent =
    lastPart.type === "text" && lastPart.text?.trim().length > 0;

  Logger.debug("All tool calls ready to send: %s", allToolCallsReady);

  return allToolCallsReady && !hasTextContent;
}

export function useFileState() {
  const [files, setFiles] = useState<File[]>([]);

  const addFiles = useEvent((newFiles: File[]) => {
    if (newFiles.length === 0) {
      return;
    }

    const totalSize = newFiles.reduce((size, file) => size + file.size, 0);
    if (totalSize > MAX_ATTACHMENT_SIZE) {
      toast({
        title: "File size exceeded",
        description: "Attachments must be under 50 MB",
        variant: "danger",
      });
      return;
    }

    setFiles((prev) => [...prev, ...newFiles]);
  });

  const clearFiles = () => setFiles([]);
  const removeFile = (fileToRemove: File) =>
    setFiles((prev) => prev.filter((f) => f !== fileToRemove));

  return { files, addFiles, clearFiles, removeFile };
}
