/* Copyright 2024 Marimo. All rights reserved. */

import type {
  Completion,
  CompletionContext,
  CompletionSource,
} from "@codemirror/autocomplete";
import type { FileUIPart } from "ai";
import { getAIContextRegistry } from "@/core/ai/context/context";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

interface Opts {
  input: string;
}

interface AICompletionBodyWithAttachments {
  body: Omit<AiCompletionRequest, "language" | "prompt" | "code">;
  attachments: FileUIPart[];
}

/**
 * Gets the request body for the AI completion API.
 */
export function getAICompletionBody({
  input,
}: Opts): Omit<AiCompletionRequest, "language" | "prompt" | "code"> {
  let contextString = "";

  // Skip if no '@' in the input
  if (input.includes("@")) {
    contextString = extractTaggedContext(input);
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
 * Gets the request body and attachments for the AI completion API.
 */
export async function getAICompletionBodyWithAttachments({
  input,
}: Opts): Promise<AICompletionBodyWithAttachments> {
  let contextString = "";
  let attachments: FileUIPart[] = [];

  // Skip if no '@' in the input
  if (input.includes("@")) {
    const registry = getAIContextRegistry(store);
    const contextIds = registry.parseAllContextIds(input);

    // Get context string
    contextString = registry.formatContextForAI(contextIds);

    // Get attachments
    try {
      attachments = await registry.getAttachmentsForContext(contextIds);
      Logger.debug("Included attachments", attachments.length);
    } catch (error) {
      Logger.error("Error getting attachments:", error);
    }
  }

  return {
    body: {
      includeOtherCode: getCodes(""),
      context: {
        plainText: contextString,
        schema: [],
        variables: [],
      },
    },
    attachments,
  };
}

/**
 * Extracts datasets, variables and other context from the input.
 * References are with @<name> in the input.
 */
function extractTaggedContext(input: string): string {
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
