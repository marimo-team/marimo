/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { streamCompletionText } from "../stream-completion-text";

function streamResponse(...chunks: object[]): Response {
  const body = [
    ...chunks.map((chunk) => `data: ${JSON.stringify(chunk)}\n\n`),
    "data: [DONE]\n\n",
  ].join("");
  return new Response(body, {
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("streamCompletionText", () => {
  it("returns validated cell code", async () => {
    const response = streamResponse(
      { type: "start" },
      {
        type: "data-cell-completion",
        data: { code: "print('```')" },
      },
      { type: "finish", finishReason: "stop" },
    );

    await expect(streamCompletionText(response)).resolves.toBe("print('```')");
  });

  it("rejects a missing structured completion", async () => {
    const response = streamResponse(
      { type: "start" },
      { type: "finish", finishReason: "stop" },
    );

    await expect(streamCompletionText(response)).rejects.toThrow(
      "AI completion returned no cell code",
    );
  });

  it("rejects malformed completion data", async () => {
    const response = streamResponse({
      type: "data-cell-completion",
      data: { code: 42 },
    });

    await expect(streamCompletionText(response)).rejects.toThrow();
  });

  it("rejects a partial completion without successful final validation", async () => {
    const response = streamResponse({
      type: "data-cell-completion",
      data: { code: "partial" },
    });

    await expect(streamCompletionText(response)).rejects.toThrow(
      "AI completion ended before final validation",
    );
  });

  it("rejects a completion with an error finish reason", async () => {
    const response = streamResponse(
      {
        type: "data-cell-completion",
        data: { code: "partial" },
      },
      { type: "finish", finishReason: "error" },
    );

    await expect(streamCompletionText(response)).rejects.toThrow(
      "AI completion ended before final validation",
    );
  });
});
