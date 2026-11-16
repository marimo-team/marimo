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
