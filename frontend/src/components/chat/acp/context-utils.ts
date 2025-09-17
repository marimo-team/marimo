/* Copyright 2024 Marimo. All rights reserved. */

import type { ContentBlock } from "@zed-industries/agent-client-protocol";
import type { FileUIPart } from "ai";
import { getAIContextRegistry } from "@/core/ai/context/context";
import { store } from "@/core/state/jotai";
import { blobToString } from "@/utils/fileToBase64";
import { Logger } from "@/utils/Logger";

export interface ContextParseResult {
  contextBlocks: ContentBlock[];
  attachmentBlocks: ContentBlock[];
}

/**
 * Converts File objects to agent protocol resource_link content blocks
 */
export async function convertFilesToResourceLinks(
  files: File[],
): Promise<ContentBlock[]> {
  const resourceLinks: ContentBlock[] = [];

  for (const file of files) {
    try {
      const dataUrl = await blobToString(file, "dataUrl");
      resourceLinks.push({
        type: "resource_link",
        uri: dataUrl,
        mimeType: file.type,
        name: file.name,
      });
    } catch (error) {
      Logger.error("Error converting file to resource link", {
        fileName: file.name,
        error,
      });
    }
  }

  return resourceLinks;
}

/**
 * Converts AI context registry attachments to agent protocol resource_link content blocks
 */
async function convertAiAttachmentsToResourceLinks(
  attachments: FileUIPart[],
): Promise<ContentBlock[]> {
  const resourceLinks: ContentBlock[] = [];

  for (const attachment of attachments) {
    resourceLinks.push({
      type: "resource_link",
      uri: attachment.url,
      mimeType: attachment.mediaType,
      name: attachment.filename ?? attachment.url,
    });
  }

  return resourceLinks;
}

/**
 * Parses context from the prompt value and returns content blocks for agent prompts.
 * Extracts context references using @ notation and converts them to resource blocks.
 * Also handles attachments from the AI context registry.
 */
export async function parseContextFromPrompt(
  promptValue: string,
): Promise<ContextParseResult> {
  const contextBlocks: ContentBlock[] = [];
  const attachmentBlocks: ContentBlock[] = [];

  // Skip if no '@' in the input
  if (!promptValue.includes("@")) {
    return { contextBlocks, attachmentBlocks };
  }

  try {
    const registry = getAIContextRegistry(store);
    const contextIds = registry.parseAllContextIds(promptValue);

    if (contextIds.length === 0) {
      return { contextBlocks, attachmentBlocks };
    }

    // Get context string for the registry
    const contextString = registry.formatContextForAI(contextIds);

    if (contextString.trim()) {
      // Create a resource block with the context information
      contextBlocks.push({
        type: "resource",
        resource: {
          uri: "context.md",
          mimeType: "text/markdown",
          text: contextString,
        },
      });
    }

    // Get attachments from the AI context registry
    try {
      const aiAttachments = await registry.getAttachmentsForContext(contextIds);
      if (aiAttachments.length > 0) {
        const resourceLinks =
          await convertAiAttachmentsToResourceLinks(aiAttachments);
        attachmentBlocks.push(...resourceLinks);
        Logger.debug("Added AI context attachments", {
          count: aiAttachments.length,
        });
      }
    } catch (error) {
      Logger.error("Error getting AI context attachments", { error });
    }

    Logger.debug("Parsed context for agent", {
      contextIds,
      contextLength: contextString.length,
      attachmentCount: attachmentBlocks.length,
    });
  } catch (error) {
    Logger.error("Error parsing context for agent", { error });
  }

  return { contextBlocks, attachmentBlocks };
}
