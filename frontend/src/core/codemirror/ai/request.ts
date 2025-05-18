/* Copyright 2024 Marimo. All rights reserved. */

import { API } from "@/core/network/api";
import { asURL } from "@/utils/url";
import type { LanguageAdapterType } from "../language/types";
import type { AiCompletionRequest } from "@/core/network/types";

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

  const response = await fetch(asURL("api/ai/completion").toString(), {
    method: "POST",
    headers: API.headers(),
    body: JSON.stringify({
      prompt: opts.prompt,
      code: codeWithReplacement,
      selectedText: opts.selection,
      includeOtherCode: "",
      language: opts.language,
    } satisfies AiCompletionRequest),
  });

  const firstLineIndent = opts.selection.match(/^\s*/)?.[0] || "";

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Failed to get response reader");
  }

  let result = "";
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    result += new TextDecoder().decode(value);
  }

  // Add back the indent if it was stripped, which can happen with
  // LLM responses
  if (!result.startsWith(firstLineIndent)) {
    result = firstLineIndent + result;
  }

  return result;
}
