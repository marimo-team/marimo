/* Copyright 2026 Marimo. All rights reserved. */

import { consumeStream, parseJsonEventStream, uiMessageChunkSchema } from "ai";
import {
  CELL_COMPLETION_DATA_TYPE,
  cellCompletionSchema,
  isDataChunk,
} from "./completion-output";

/**
 * Read an AI SDK UI message stream response and return validated cell code.
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

  let result: string | null = null;
  let finishedSuccessfully = false;

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
          if (
            isDataChunk(streamPart) &&
            streamPart.type === CELL_COMPLETION_DATA_TYPE
          ) {
            result = cellCompletionSchema.parse(streamPart.data).code;
          } else if (streamPart.type === "error") {
            throw new Error(streamPart.errorText);
          } else if (streamPart.type === "finish") {
            finishedSuccessfully = streamPart.finishReason === "stop";
          }
        },
      }),
    ),
    onError: (error) => {
      throw error;
    },
  });

  if (!finishedSuccessfully) {
    throw new Error("AI completion ended before final validation");
  }
  if (result === null) {
    throw new Error("AI completion returned no cell code");
  }

  return result;
}
