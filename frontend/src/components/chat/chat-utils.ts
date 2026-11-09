/* Copyright 2026 Marimo. All rights reserved. */

import type { components } from "@marimo-team/marimo-api";
import type { ChatAddToolOutputFunction, FileUIPart, UIMessage } from "ai";
import { useState } from "react";
import useEvent from "react-use-event-hook";
import { z } from "zod";
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

const toolArgumentsSchema = z.record(z.string(), z.unknown());

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
    input: unknown;
  };
  toolContext: ToolNotebookContext;
}) {
  try {
    const response = FRONTEND_TOOL_REGISTRY.has(toolCall.toolName)
      ? await FRONTEND_TOOL_REGISTRY.invoke({
          toolName: toolCall.toolName,
          rawArgs: toolCall.input,
          toolContext,
        })
      : await invokeAiTool({
          toolName: toolCall.toolName,
          arguments: toolArgumentsSchema.parse(toolCall.input ?? {}),
        });
    addToolOutput({
      tool: toolCall.toolName,
      toolCallId: toolCall.toolCallId,
      ...(response.error
        ? { state: "output-error", errorText: response.error }
        : { output: response.result }),
    });
  } catch (error) {
    Logger.error("Tool call failed:", error);
    addToolOutput({
      tool: toolCall.toolName,
      toolCallId: toolCall.toolCallId,
      state: "output-error",
      errorText: error instanceof Error ? error.message : String(error),
    });
  }
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
