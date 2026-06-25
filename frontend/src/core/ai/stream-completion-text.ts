/* Copyright 2026 Marimo. All rights reserved. */

import { consumeStream, parseJsonEventStream, uiMessageChunkSchema } from "ai";
import { stripWrappingBackticks } from "./strip-wrapping-backticks";

/**
 * Read an AI SDK UI message stream response and return the assistant text.
 */
export async function streamCompletionText(
  response: Response,
): Promise<string> {
  if (!response.ok) {
    throw new Error(await response.text());
  }

  if (!response.body) {
    throw new Error("Failed to get response body");
  }

  let result = "";

  await consumeStream({
    stream: parseJsonEventStream({
      stream: response.body,
      schema: uiMessageChunkSchema,
    }).pipeThrough(
      new TransformStream({
        transform(part) {
          if (!part.success) {
            throw part.error;
          }

          const streamPart = part.value;
          if (streamPart.type === "text-delta") {
            result += streamPart.delta;
          } else if (streamPart.type === "error") {
            throw new Error(streamPart.errorText);
          }
        },
      }),
    ),
    onError: (error) => {
      throw error;
    },
  });

  return stripWrappingBackticks(result);
}
