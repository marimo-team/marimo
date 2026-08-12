/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { Resource } from "@marimo-team/codemirror-mcp";
import type { FileUIPart } from "ai";
import { Memoize } from "typescript-memoize";
import { Logger } from "@/utils/Logger";
import { MultiMap } from "@/utils/multi-map";
import type { TypedString } from "@/utils/typed";

/**
 * Unique identifier for a context item in the format "type://id"
 * e.g., "variable://my_var", "data://users", "file://config.py"
 */
export type ContextLocatorId = TypedString<"ContextLocatorId">;

function parseContextType(uri: ContextLocatorId): string | undefined {
  const separator = uri.indexOf("://");
  if (separator === -1) {
    return undefined;
  }
  return uri.slice(0, separator);
}

/**
 * Base interface for context items that can be mentioned in AI prompts
 */
export interface AIContextItem extends Resource<Record<string, unknown>> {
  data: Record<string, unknown>;
}

/**
 * Abstract base class for AI context providers with shared implementation
 */
export abstract class AIContextProvider<
  T extends AIContextItem = AIContextItem,
> {
  /** Human-readable title for this context type */
  abstract readonly title: string;

  /** Prefix used for mentions (e.g., "@" for variables, "#" for files) */
  abstract readonly mentionPrefix: "@" | "#";

  /** Context type identifier used in ContextLocatorId */
  abstract readonly contextType: string;

  /** Get all available items of this context type */
  abstract getItems(): T[];

  /** Format the context for inclusion in AI prompt */
  abstract formatContext(item: T): string;

  /** Format completion */
  abstract formatCompletion(item: T): Completion;

  /** Get attachments for context items (optional, async) */
  async getAttachments(_items: T[]): Promise<FileUIPart[]> {
    // Default implementation returns no attachments
    return [];
  }

  asURI(id: string): ContextLocatorId {
    return `${this.contextType}://${id}` as ContextLocatorId;
  }

  /** Parse context IDs from input text using the provider's mention prefix */
  parseContextIds(input: string): ContextLocatorId[] {
    // Match @type://id, e.g., @data://users
    const regex = new RegExp(
      `${this.mentionPrefix}([\\w-]+):\\/\\/([\\w./-]+)`,
      "g",
    );
    const matches = [...input.matchAll(regex)];
    const justURI = (match: string) => match.slice(1);

    const results = matches
      .filter(([, type]) => type === this.contextType)
      .map(([matchString]) => justURI(matchString) as ContextLocatorId);

    return [...new Set(results)];
  }

  /** Create a basic completion object - can be used by subclasses */
  protected createBasicCompletion(
    item: T,
    options?: {
      boost?: number;
      type?: string;
      section?: string;
      detail?: string;
    },
  ): Completion {
    return {
      label: `${this.mentionPrefix}${item.uri.split("://")[1]}`,
      displayLabel: item.name,
      detail: options?.detail || item.description,
      boost: options?.boost || 1,
      type: options?.type || this.contextType,
      apply: `${this.mentionPrefix}${item.uri}`,
      section: options?.section || this.title,
    };
  }
}

/**
 * Registry for managing different AI context providers
 */
export class AIContextRegistry<T extends AIContextItem> {
  // oxlint-disable-next-line typescript/no-explicit-any
  private providers = new Set<AIContextProvider<any>>();

  /**
   * Register a new context provider
   */
  register<U extends AIContextItem>(
    provider: AIContextProvider<U>,
    // oxlint-disable-next-line typescript/prefer-return-this-type
  ): AIContextRegistry<U | T> {
    this.providers.add(provider);
    return this;
  }

  /**
   * Get all registered providers
   */
  getProviders(): Set<AIContextProvider<T>> {
    return this.providers;
  }

  /**
   * Get a specific provider by type
   */
  getProvider(type: string): AIContextProvider | undefined {
    return [...this.providers].find(
      (provider) => provider.contextType === type,
    );
  }

  @Memoize()
  getAllItems(): T[] {
    return [...this.providers].flatMap((provider) => provider.getItems());
  }

  /**
   * Parse context IDs from input across all providers
   */
  parseAllContextIds(input: string): ContextLocatorId[] {
    return [...this.providers].flatMap((provider) =>
      provider.parseContextIds(input),
    );
  }

  private findProviderForUri(
    uri: ContextLocatorId,
  ): AIContextProvider | undefined {
    const type = parseContextType(uri);
    if (!type) {
      return undefined;
    }
    return [...this.providers].find(
      (provider) =>
        provider.contextType === type &&
        provider.getItems().some((item) => item.uri === uri),
    );
  }

  /**
   * Resolve only the requested context items, querying each matching provider
   */
  resolveItems(contextIds: ContextLocatorId[]): T[] {
    if (contextIds.length === 0) {
      return [];
    }

    const idsByType = new MultiMap<string, ContextLocatorId>();
    for (const contextId of contextIds) {
      const type = parseContextType(contextId);
      if (type) {
        idsByType.add(type, contextId);
      }
    }

    const itemsById = new Map<ContextLocatorId, T>();
    for (const [type, ids] of idsByType.entries()) {
      const providers = [...this.providers].filter(
        (provider) => provider.contextType === type,
      );
      for (const provider of providers) {
        const itemsByUri = new Map<ContextLocatorId, T>(
          provider
            .getItems()
            .map((item) => [item.uri as ContextLocatorId, item as T]),
        );
        for (const id of ids) {
          const item = itemsByUri.get(id);
          if (item) {
            itemsById.set(id, item);
          }
        }
      }
    }

    // Preserve the order in which the ids were requested, so formatted context
    // matches the order the user mentioned them in the prompt.
    const results: T[] = [];
    for (const contextId of contextIds) {
      const item = itemsById.get(contextId);
      if (item) {
        results.push(item);
      }
    }
    return results;
  }

  /**
   * Get context information for mentioned items
   */
  getContextInfo(contextIds: ContextLocatorId[]): T[] {
    return this.resolveItems(contextIds);
  }

  /**
   * Format context for AI prompt inclusion
   */
  formatContextForAI(contextIds: ContextLocatorId[]): string {
    const contextInfo = this.resolveItems(contextIds);

    if (contextInfo.length === 0) {
      return "";
    }

    return contextInfo
      .map((item) => {
        const provider = this.findProviderForUri(item.uri as ContextLocatorId);
        return provider?.formatContext(item) || "";
      })
      .join("\n\n");
  }

  /**
   * Get attachments for mentioned items
   */
  async getAttachmentsForContext(
    contextIds: ContextLocatorId[],
  ): Promise<FileUIPart[]> {
    const contextInfo = this.resolveItems(contextIds);

    if (contextInfo.length === 0) {
      return [];
    }

    const itemsByProvider = new MultiMap<AIContextProvider, T>();
    for (const item of contextInfo) {
      const provider = this.findProviderForUri(item.uri as ContextLocatorId);
      if (provider) {
        itemsByProvider.add(provider, item);
      }
    }

    const attachmentPromises = [...itemsByProvider.entries()].map(
      async ([provider, items]) => {
        try {
          return await provider.getAttachments(items);
        } catch (error) {
          Logger.error("Error getting attachments from provider", error);
          return [];
        }
      },
    );

    const attachmentResults = await Promise.all(attachmentPromises);
    const results = attachmentResults.flat();

    // Print attachments to the console with a rich image preview
    if (import.meta.env.DEV) {
      for (const attachment of results) {
        // If it's an image, print a rich preview
        if (
          /^data:image\/(png|jpeg|jpg|gif|svg\+xml);base64,/.test(
            attachment.url,
          )
        ) {
          Logger.debug(
            "%c ",
            `font-size:1px;padding:140px 180px;background:url('${attachment.url}') no-repeat;background-size:contain;`,
          );
        }
      }
    }

    return results;
  }
}
