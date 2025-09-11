/* Copyright 2024 Marimo. All rights reserved. */

import {
  type Completion,
  type CompletionContext,
  type CompletionSource,
  startCompletion,
} from "@codemirror/autocomplete";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type { FileUIPart, UIMessage } from "ai";
import { getAIContextRegistry } from "@/core/ai/context/context";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import type { AiCompletionRequest } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

export const CONTEXT_TRIGGER = "@";

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

export function addContextCompletion(
  inputRef: React.RefObject<ReactCodeMirrorRef | null>,
) {
  if (inputRef.current?.view) {
    const pos = inputRef.current.view.state.selection.main.from;
    // Insert @ at the cursor position
    inputRef.current.view.dispatch({
      changes: {
        from: pos,
        to: pos,
        insert: CONTEXT_TRIGGER,
      },
      selection: {
        anchor: pos + 1,
        head: pos + 1,
      },
    });
    inputRef.current.view.focus();
    // Trigger completion
    startCompletion(inputRef.current.view);
  }
}

export type Language = "python" | "sql" | "markdown";

export interface AiCompletion {
  language: Language;
  code: string;
}

/**
 * Extracts code blocks (delimited by triple backticks) and their language ("python", "sql", "markdown").
 * Defaults to "python" if no language is specified or no code blocks are found.
 * Returns an array of AiCompletion objects.
 */
export function splitCodeIntoCells(code: string): AiCompletion[] {
  const cells: AiCompletion[] = [];
  let start = 0;

  let openIndex = code.indexOf("```", start);
  while (openIndex !== -1) {
    const newlineIndex = code.indexOf("\n", openIndex);
    if (newlineIndex === -1) {
      break;
    }

    let language = code.slice(openIndex + 3, newlineIndex).trim() || "";
    language =
      language === "markdown"
        ? "markdown"
        : language === "sql"
          ? "sql"
          : "python";
    const codeStart = newlineIndex + 1;

    const closeIndex = code.indexOf("```", codeStart);
    if (closeIndex === -1) {
      break;
    }

    // Remove trailing newlines
    const codeContent = code.slice(codeStart, closeIndex).replace(/\n+$/, "");
    if (codeContent) {
      cells.push({ language: language as Language, code: codeContent });
    }

    start = closeIndex + 3;
    openIndex = code.indexOf("```", start);
  }

  // If no cells found, assume code is in 1 cell and python
  if (cells.length === 0) {
    cells.push({ language: "python", code: code });
  }

  return cells;
}

export function UIMessageToCodeCells(message: UIMessage): AiCompletion[] {
  const textParts = message.parts?.filter((p) => p.type === "text");
  const textResponse = textParts?.map((p) => p.text).join("\n");
  return splitCodeIntoCells(textResponse);
}
