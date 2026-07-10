/* Copyright 2026 Marimo. All rights reserved. */

import {
  type Completion,
  type CompletionContext,
  type CompletionSource,
  startCompletion,
} from "@codemirror/autocomplete";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type { DataUIPart, FileUIPart, UIMessage } from "ai";
import { getAIContextRegistry } from "@/core/ai/context/context";
import type { ContextLocatorId } from "@/core/ai/context/registry";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
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

export interface MarimoContextData {
  plainText: string;
  contextIds: string[];
}

export type MarimoContextUIPart = DataUIPart<{
  "marimo-context": MarimoContextData;
}>;

/**
 * Wire `type` of the @-context data part. Must match
 * `MARIMO_CONTEXT_PART_TYPE` on the backend.
 */
export const MARIMO_CONTEXT_PART_TYPE =
  "data-marimo-context" as const satisfies MarimoContextUIPart["type"];

export interface ResolvedChatContext {
  contextPart: MarimoContextUIPart | null;
  attachments: FileUIPart[];
}

/**
 * Marker stamped onto attachments derived from @-context (as opposed to files
 * the user uploaded directly).
 */
const CONTEXT_ATTACHMENT_METADATA = {
  marimo: { source: "context" },
} as const;

/** Whether a part is an attachment that was derived from @-context. */
export function isContextAttachment(part: UIMessage["parts"][number]): boolean {
  return (
    part.type === "file" &&
    part.providerMetadata?.marimo?.source ===
      CONTEXT_ATTACHMENT_METADATA.marimo.source
  );
}

/**
 * Stamp a context-derived attachment with a provenance marker.
 *
 * Some @-mentions resolve to file attachments (e.g. a cell's image output),
 * which get appended to the user message right alongside files the user
 * uploaded by hand. Once they're in the message the two are indistinguishable,
 * so we mark the context-derived ones. This matters on message edit: we
 * re-resolve context from the edited text, and `isContextAttachment` lets us
 * drop only the stale context attachments while preserving the user's own
 * uploads
 */
function stampContextAttachment(attachment: FileUIPart): FileUIPart {
  return {
    ...attachment,
    providerMetadata: {
      ...attachment.providerMetadata,
      // Merge within the `marimo` namespace so we don't clobber any other
      // marimo metadata a provider may have already set.
      marimo: {
        ...attachment.providerMetadata?.marimo,
        ...CONTEXT_ATTACHMENT_METADATA.marimo,
      },
    },
  };
}

interface ResolvedContext {
  plainText: string;
  contextIds: ContextLocatorId[];
  attachments: FileUIPart[];
}

/**
 * Parse @-context for messages
 */
async function resolveContextAttachments(
  input: string,
): Promise<ResolvedContext> {
  if (!input.includes(CONTEXT_TRIGGER)) {
    return { plainText: "", contextIds: [], attachments: [] };
  }

  const registry = getAIContextRegistry(store);
  const contextIds = registry.parseAllContextIds(input);
  if (contextIds.length === 0) {
    return { plainText: "", contextIds: [], attachments: [] };
  }

  const plainText = registry.formatContextForAI(contextIds);

  let attachments: FileUIPart[] = [];
  try {
    const resolved = await registry.getAttachmentsForContext(contextIds);
    attachments = resolved.map(stampContextAttachment);
  } catch (error) {
    Logger.error("Error getting attachments:", error);
  }

  return { plainText, contextIds, attachments };
}

/**
 * Resolve @-context for messages. They represent referenced
 * datasets, variables, or other context from the user's prompt.
 */
export async function resolveChatContext(
  input: string,
): Promise<ResolvedChatContext> {
  const { plainText, contextIds, attachments } =
    await resolveContextAttachments(input);

  let contextPart: MarimoContextUIPart | null = null;
  if (plainText.trim()) {
    contextPart = {
      type: MARIMO_CONTEXT_PART_TYPE,
      data: { plainText, contextIds: contextIds.map(String) },
    };
  }

  return { contextPart, attachments };
}

/**
 * Gets the request body and attachments for the AI completion API.
 */
export async function getAICompletionBodyWithAttachments({
  input,
}: Opts): Promise<AICompletionBodyWithAttachments> {
  const { plainText, attachments } = await resolveContextAttachments(input);

  return {
    body: {
      includeOtherCode: getCodes(""),
      context: {
        plainText,
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

export interface AiCompletion {
  language: LanguageAdapterType;
  code: string;
}

/**
 * Extracts code blocks (delimited by triple backticks) and their language ("python", "sql", "markdown").
 * Defaults to "python" if no language is specified or no code blocks are found.
 * Returns an array of AiCompletion objects.
 */
export function codeToCells(code: string): AiCompletion[] {
  if (code.trim().length === 0) {
    return [];
  }

  // If there are no backticks, assume code is in 1 cell and python
  if (!code.includes("```")) {
    return [{ language: "python", code: code }];
  }

  // If code has opening backticks, get the code after it
  const cells: AiCompletion[] = [];
  let start = 0;

  let openIndex = code.indexOf("```", start);
  while (openIndex !== -1) {
    const newlineIndex = code.indexOf("\n", openIndex);
    if (newlineIndex === -1) {
      // If there's no newline after opening backticks, treat everything after as code
      const remaining = code.slice(openIndex + 3);
      const firstSpace = remaining.indexOf(" ");
      const language =
        firstSpace === -1 ? remaining : remaining.slice(0, firstSpace);
      const finalLanguage =
        language === "markdown"
          ? "markdown"
          : language === "sql"
            ? "sql"
            : "python";
      // Extract code after the language identifier
      const codeContent =
        firstSpace === -1 ? "" : remaining.slice(firstSpace + 1);
      if (codeContent.trim()) {
        cells.push({ language: finalLanguage, code: codeContent.trim() });
      }
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
      // If there's no closing backticks, treat everything after the opening as code
      const codeContent = code.slice(codeStart).replace(/\n+$/, "");
      if (codeContent.trim()) {
        cells.push({
          language: language as LanguageAdapterType,
          code: codeContent,
        });
      }
      break;
    }

    // Remove trailing newlines
    const codeContent = code.slice(codeStart, closeIndex).replace(/\n+$/, "");
    if (codeContent.trim()) {
      cells.push({
        language: language as LanguageAdapterType,
        code: codeContent,
      });
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
