/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { Resource } from "@marimo-team/codemirror-mcp";
import type { FileUIPart } from "ai";
import { Memoize } from "typescript-memoize";
import { Logger } from "@/utils/Logger";
import { MultiMap } from "@/utils/multi-map";
import type { TypedString } from "@/utils/typed";

/**
 * Unique identifier for a context item in the format "type:id"
 * e.g., "variable://my_var", "data://users", "file://config.py"
 */
export type ContextLocatorId = TypedString<"ContextLocatorId">;

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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private providers = new Set<AIContextProvider<any>>();

  /**
   * Register a new context provider
   */
  register<U extends AIContextItem>(
    provider: AIContextProvider<U>,
    // eslint-disable-next-line @typescript-eslint/prefer-return-this-type
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

  /**
   * Get context information for mentioned items
   */
  getContextInfo(contextIds: ContextLocatorId[]): T[] {
    const contextInfo: T[] = [];
    const allItems = new Map<ContextLocatorId, T>(
      this.getAllItems().map((item) => [item.uri as ContextLocatorId, item]),
    );

    for (const contextId of contextIds) {
      const item = allItems.get(contextId);
      if (item) {
        contextInfo.push(item);
      }
    }

    return contextInfo;
  }

  /**
   * Format context for AI prompt inclusion
   */
  formatContextForAI(contextIds: ContextLocatorId[]): string {
    const allItems = new Map<ContextLocatorId, T>(
      this.getAllItems().map((item) => [item.uri as ContextLocatorId, item]),
    );

    const contextInfo: T[] = [];
    for (const contextId of contextIds) {
      const item = allItems.get(contextId);
      if (item) {
        contextInfo.push(item);
      }
    }

    if (contextInfo.length === 0) {
      return "";
    }

    return contextInfo
      .map((item) => {
        const provider = this.getProvider(item.type);
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
    const allItems = new Map<ContextLocatorId, T>(
      this.getAllItems().map((item) => [item.uri as ContextLocatorId, item]),
    );

    const contextInfo: T[] = [];
    for (const contextId of contextIds) {
      const item = allItems.get(contextId);
      if (item) {
        contextInfo.push(item);
      }
    }

    if (contextInfo.length === 0) {
      return [];
    }

    // Group items by provider type to batch attachment requests
    const itemsByProvider = new MultiMap<string, T>();
    for (const item of contextInfo) {
      const providerType = item.type;
      itemsByProvider.add(providerType, item);
    }

    // Collect attachments from all providers
    const attachmentPromises = [...itemsByProvider.entries()].map(
      async ([providerType, items]) => {
        const provider = this.getProvider(providerType);
        if (!provider) {
          return [];
        }
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
