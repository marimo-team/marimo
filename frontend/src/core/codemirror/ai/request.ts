/* Copyright 2026 Marimo. All rights reserved. */

import { waitForConnectionOpen } from "@/core/network/connection";
import type { AiCompletionRequest } from "@/core/network/types";
import { streamCompletionText } from "@/core/ai/stream-completion-text";
import { getRuntimeManager } from "@/core/runtime/config";
import type { LanguageAdapterType } from "../language/types";

/**
 * Request to edit code with AI
 */
export async function requestEditCompletion(opts: {
  prompt: string;
  selection: string;
  codeBefore: string;
  codeAfter: string;
  language: LanguageAdapterType;
}): Promise<string> {
  // TODO: maybe include other code
  // const otherCodes = getCodes(currentCode);

  const codeWithReplacement = `
${opts.codeBefore}
<rewrite_this>
${opts.selection}
</rewrite_this>
${opts.codeAfter}
`.trim();

  const runtimeManager = getRuntimeManager();

  await waitForConnectionOpen();

  const response = await fetch(
    runtimeManager.getAiURL("completion").toString(),
    {
      method: "POST",
      headers: runtimeManager.headers(),
      body: JSON.stringify({
        prompt: opts.prompt,
        code: codeWithReplacement,
        selectedText: opts.selection,
        includeOtherCode: "",
        language: opts.language,
      } satisfies AiCompletionRequest),
    },
  );

  const firstLineIndent = opts.selection.match(/^\s*/)?.[0] || "";

  let result = await streamCompletionText(response);

  // Add back the indent if it was stripped, which can happen with
  // LLM responses
  if (!result.startsWith(firstLineIndent)) {
    result = firstLineIndent + result;
  }

  return result;
}
