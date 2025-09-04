/* Copyright 2024 Marimo. All rights reserved. */

import type { FileUIPart, UIMessage } from "ai";
import { blobToString } from "@/utils/fileToBase64";

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
