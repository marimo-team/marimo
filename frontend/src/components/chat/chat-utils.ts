/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import type { FileUIPart, ToolUIPart, UIMessage } from "ai";
import { useState } from "react";
import useEvent from "react-use-event-hook";
import type { ProviderId } from "@/core/ai/ids/ids";
import type { ToolNotebookContext } from "@/core/ai/tools/base";
import { FRONTEND_TOOL_REGISTRY } from "@/core/ai/tools/registry";
import type {
  InvokeAiToolRequest,
  InvokeAiToolResponse,
} from "@/core/network/types";
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

interface AddToolOutput {
  tool: string;
  toolCallId: string;
  output: unknown;
}

export async function handleToolCall({
  invokeAiTool,
  addToolOutput, // Important that we don't await addToolOutput to prevent potential deadlocks
  toolCall,
  toolContext,
}: {
  invokeAiTool: (request: InvokeAiToolRequest) => Promise<InvokeAiToolResponse>;
  addToolOutput: (output: AddToolOutput) => Promise<void>;
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
      const response = await FRONTEND_TOOL_REGISTRY.invoke(
        toolCall.toolName,
        toolCall.input,
        toolContext,
      );
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

export function useFileState() {
  const [files, setFiles] = useState<File[]>([]);

  const onAddFiles = useEvent((newFiles: File[]) => {
    if (newFiles.length === 0) {
      return;
    }

    let fileSize = 0;
    for (const file of newFiles) {
      fileSize += file.size;
    }

    if (fileSize > MAX_ATTACHMENT_SIZE) {
      toast({
        title: "File size exceeds 50MB limit",
        variant: "danger",
      });
      return;
    }

    setFiles((prev) => [...(prev ?? []), ...newFiles]);
  });

  const removeFile = (fileToRemove: File) => {
    setFiles((prev) => (prev ?? []).filter((f) => f !== fileToRemove));
  };

  return { files, setFiles, onAddFiles, removeFile };
}
