/* Copyright 2024 Marimo. All rights reserved. */

import { API } from "@/core/network/api";
import { asURL } from "@/utils/url";
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

  const finalPrompt = `
Given the following code context, ${opts.prompt}

SELECTED CODE:
${opts.selection}

CODE BEFORE SELECTION:
${opts.codeBefore}

CODE AFTER SELECTION:
${opts.codeAfter}

Instructions:
1. Modify ONLY the selected code
2. Keep the same indentation selected code
3. Maintain consistent style with surrounding code
4. Ensure the edit is complete and can be inserted directly
5. Return ONLY the replacement code, no explanations, no code fences.

Your task: ${opts.prompt}`;

  const response = await fetch(asURL("api/ai/completion").toString(), {
    method: "POST",
    headers: API.headers(),
    body: JSON.stringify({
      prompt: finalPrompt,
      code: "",
      includeOtherCode: "",
      language: opts.language,
    }),
  });

  const firstLineIndent = /^\s*/.exec(opts.selection)?.[0] || "";

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
