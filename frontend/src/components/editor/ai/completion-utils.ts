/* Copyright 2024 Marimo. All rights reserved. */

import type {
  Completion,
  CompletionContext,
  CompletionSource,
} from "@codemirror/autocomplete";
import { getAIContextRegistry } from "@/core/ai/context/context";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

/**
 * Gets the request body for the AI completion API.
 */
export function getAICompletionBody({
  input,
}: {
  input: string;
}): Omit<AiCompletionRequest, "language" | "prompt" | "code"> {
  let contextString = "";
  // Skip if no '@' in the input
  if (input.includes("@")) {
    contextString = extractDatasetsAndVariables(input);
    Logger.debug("Included context", contextString);
  }

  return {
    includeOtherCode: getCodes(""),
    context: {
      plainText: contextString,
      schema: [],
      variables: [],
    },
  };
}

/**
 * Extracts datasets and variables from the input.
 * References are with @<name> in the input.
 * Prioritizes datasets over variables if there's a name conflict.
 */
function extractDatasetsAndVariables(input: string): string {
  const registry = getAIContextRegistry(store);
  const contextIds = registry.parseAllContextIds(input);
  return registry.formatContextForAI(contextIds);
}

/**
 * Adapted from @uiw/codemirror-extensions-mentions
 * Allows you to specify a custom regex to trigger the autocompletion.
 */
export function mentionsCompletionSource(
  matchBeforeRegexes: RegExp[],
  data: Completion[] = [],
): CompletionSource {
  return (context: CompletionContext) => {
    const word = matchBeforeRegexes
      .map((regex) => context.matchBefore(regex))
      .find(Boolean);
    if (!word) {
      return null;
    }
    if (word && word.from === word.to && !context.explicit) {
      return null;
    }
    return {
      from: word?.from,
      options: [...data],
    };
  };
}
