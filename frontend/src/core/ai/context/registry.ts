/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { Resource } from "@marimo-team/codemirror-mcp";
import type { TypedString } from "@/utils/typed";

/**
 * Unique identifier for a context item in the format "type:id"
 * e.g., "variable:my_var", "table:users", "file:config.py"
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

  /** Format a context locator ID for this item */
  formatContextId(item: T): ContextLocatorId {
    return `${this.contextType}:${item.uri}` as ContextLocatorId;
  }

  asURI(id: string): string {
    return `${this.contextType}://${id}`;
  }

  /** Parse context IDs from input text using the provider's mention prefix */
  parseContextIds(input: string): ContextLocatorId[] {
    const escapedPrefix = this.mentionPrefix.replaceAll(
      /[$()*+.?[\\\]^{|}]/g,
      "\\$&",
    );
    const regex = new RegExp(`${escapedPrefix}([\\w.\\-_/]+)`, "g");
    const mentions = input.match(regex) || [];
    const items = this.getItems();

    return mentions
      .map((mention) => mention.slice(this.mentionPrefix.length))
      .filter((name) => items.some((item) => item.uri === name))
      .map((name) => this.formatContextId({ uri: name } as T));
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
      label: `${this.mentionPrefix}${item.uri}`,
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

    for (const contextId of contextIds) {
      const [type, id] = contextId.split(":", 2);
      const provider = [...this.providers].find(
        (provider) => provider.contextType === type,
      );

      if (provider) {
        const items = provider.getItems();
        const item = items.find((item) => item.uri === id);
        if (item) {
          contextInfo.push(item);
        }
      }
    }

    return contextInfo;
  }

  /**
   * Format context for AI prompt inclusion
   */
  formatContextForAI(contextIds: ContextLocatorId[]): string {
    // Map: providerType -> Set<id>
    const providerIdMap = new Map<string, Set<string>>();
    for (const contextId of contextIds) {
      const [type, id] = contextId.split(":", 2);
      if (!providerIdMap.has(type)) {
        providerIdMap.set(type, new Set());
      }
      providerIdMap.get(type)?.add(id);
    }

    const sections: string[] = [];
    for (const provider of this.providers) {
      const ids = providerIdMap.get(provider.contextType);
      if (!ids || ids.size === 0) {
        continue;
      }
      const items = provider.getItems();
      for (const item of items) {
        if (ids.has(item.uri)) {
          sections.push(provider.formatContext(item));
        }
      }
    }

    return sections.join("\n\n");
  }
}
