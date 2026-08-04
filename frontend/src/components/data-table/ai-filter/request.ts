/* Copyright 2026 Marimo. All rights reserved. */

import { streamCompletionText } from "@/core/ai/stream-completion-text";
import { waitForConnectionOpen } from "@/core/network/connection";
import type { AiCompletionRequest } from "@/core/network/types";
import type { RuntimeManager } from "@/core/runtime/runtime";

/**
 * Ask the configured LLM to translate a natural-language prompt into an FQL
 * query, via `/api/ai/completion`. If output quality is poor, switch to
 * `/api/ai/chat`.
 */
export async function requestAiFilterQuery(opts: {
  prompt: string;
  runtimeManager: RuntimeManager;
  signal?: AbortSignal;
}): Promise<string> {
  await waitForConnectionOpen();

  const response = await fetch(
    opts.runtimeManager.getAiURL("completion").toString(),
    {
      method: "POST",
      headers: opts.runtimeManager.headers(),
      signal: opts.signal,
      body: JSON.stringify({
        prompt: opts.prompt,
        code: "",
        selectedText: null,
        includeOtherCode: "",
        language: "python",
      } satisfies AiCompletionRequest),
    },
  );

  const raw = await streamCompletionText(response);
  return extractFilterQuery(raw);
}

/**
 * Pull the filter query out of a completion response: prefer the first line
 * that looks like a filter expression, else fall back to the first line.
 */
export function extractFilterQuery(raw: string): string {
  const text = raw.trim();
  if (text.length === 0) {
    throw new Error("AI returned an empty filter query.");
  }
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const looksLikeFilter = (line: string) =>
    /^(?:NOT\s+)?\(*[\p{L}\p{N}_.$-]+\s*(?:!=|>=|<=|[:=<>])\s*\S/u.test(line);
  return (lines.find(looksLikeFilter) ?? lines[0]).trim();
}
