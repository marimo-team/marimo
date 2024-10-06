/* Copyright 2024 Marimo. All rights reserved. */

import { API } from "@/core/network/api";
import { asURL } from "@/utils/url";
import type { LanguageAdapterType } from "../language/types";
import { getCodes } from "../copilot/getCodes";

/**
 * Request to edit code with AI
 */
export async function requestEditCompletion(opts: {
  prompt: string;
  selection: string;
  code: string;
  codeBefore: string;
  language: LanguageAdapterType;
}): Promise<string> {
  const currentCode = opts.code;

  const otherCodes = getCodes(currentCode);
  // Other code to include is the codeBefore and the other codes
  const includeOtherCode = `${opts.codeBefore}\n${otherCodes}`;

  const response = await fetch(asURL("api/ai/completion").toString(), {
    method: "POST",
    headers: API.headers(),
    body: JSON.stringify({
      prompt: opts.prompt,
      code: opts.selection,
      includeOtherCode: includeOtherCode,
      language: opts.language,
    }),
  });

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

  return result;
}
