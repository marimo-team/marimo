/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { Resource } from "@marimo-team/codemirror-mcp";
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
  abstract readonly mentionPrefix: string;

  /** Context type identifier used in ContextLocatorId */
  abstract readonly contextType: string;

  /** Get all available items of this context type */
  abstract getItems(): T[];

  /** Format the context for inclusion in AI prompt */
  abstract formatContext(item: T): string;

  /** Generate CodeMirror completions for autocomplete - can be overridden for custom behavior */
  abstract getCompletions(): Completion[];

  /** Format completion */
  abstract formatCompletion(item: T): Completion;

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

  /**
   * Get all completions from all providers
   */
  getAllCompletions(): Completion[] {
    return [...this.providers].flatMap((provider) => provider.getCompletions());
  }

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
}
