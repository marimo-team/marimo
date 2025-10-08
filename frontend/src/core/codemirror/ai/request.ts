/* Copyright 2024 Marimo. All rights reserved. */

import type { QualifiedModelId } from "@/core/ai/ids/ids";
import { AiModelRegistry } from "@/core/ai/model-registry";
import { aiAtom } from "@/core/config/config";
import { waitForConnectionOpen } from "@/core/network/connection";
import type { AiCompletionRequest } from "@/core/network/types";
import { getRuntimeManager } from "@/core/runtime/config";
import { store } from "@/core/state/jotai";
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

  // Get AI config and create model registry
  const ai = store.get(aiAtom);
  const aiModelRegistry = AiModelRegistry.create({
    customModels: ai?.models?.custom_models,
    displayedModels: ai?.models?.displayed_models,
    inferenceProfiles: ai?.models?.inference_profiles || {},
  });

  // Get full model ID with inference profile
  const editModel = ai?.models?.edit_model;
  const fullModelId = editModel
    ? aiModelRegistry.getFullModelId(editModel as QualifiedModelId)
    : undefined;

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
        model: fullModelId,
      } satisfies AiCompletionRequest),
    },
  );

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
