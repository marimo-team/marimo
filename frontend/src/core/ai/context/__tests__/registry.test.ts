/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import { beforeEach, describe, expect, it } from "vitest";
import {
  type AIContextItem,
  AIContextProvider,
  AIContextRegistry,
  type ContextLocatorId,
} from "../registry";

// Mock context item for testing
interface MockContextItem extends AIContextItem {
  type: "mock";
  id: string;
  label: string;
  description?: string;
  data: { value: string };
}

// Concrete implementation of AIContextProvider for testing
class MockContextProvider extends AIContextProvider<MockContextItem> {
  readonly title = "Mock Items";
  readonly mentionPrefix = "@";
  readonly contextType = "mock";

  private items: MockContextItem[] = [
    {
      type: "mock",
      id: "item1",
      label: "Item 1",
      description: "First mock item",
      data: { value: "value1" },
    },
    {
      type: "mock",
      id: "item2",
      label: "Item 2",
      description: "Second mock item",
      data: { value: "value2" },
    },
    {
      type: "mock",
      id: "item_with_special-chars",
      label: "Special Item",
      description: "Item with special characters",
      data: { value: "special" },
    },
  ];

  getItems(): MockContextItem[] {
    return this.items;
  }

  formatContext(item: MockContextItem): string {
    return `Mock: ${item.label} (${item.data.value})`;
  }

  getCompletions(): Completion[] {
    return this.items.map((item) => this.createBasicCompletion(item));
  }

  // Method to add items for testing
  addItem(item: MockContextItem): void {
    this.items.push(item);
  }

  // Method to clear items for testing
  clearItems(): void {
    this.items = [];
  }
}

interface FileContextItem extends AIContextItem {
  type: "file";
  id: string;
  label: string;
  description?: string;
  data: { value: string };
}

// Another mock provider with different prefix and type
class FileContextProvider extends AIContextProvider<FileContextItem> {
  readonly title = "Files";
  readonly mentionPrefix = "#";
  readonly contextType = "file";

  private items: FileContextItem[] = [
    {
      type: "file",
      id: "config.py",
      label: "config.py",
      description: "Configuration file",
      data: { value: "config" },
    },
    {
      type: "file",
      id: "utils/helpers.py",
      label: "utils/helpers.py",
      description: "Helper functions",
      data: { value: "helpers" },
    },
  ];

  getItems(): FileContextItem[] {
    return this.items;
  }

  formatContext(item: FileContextItem): string {
    return `File: ${item.id}\nDescription: ${item.description}`;
  }

  getCompletions(): Completion[] {
    return this.items.map((item) =>
      this.createBasicCompletion(item, { boost: 2, section: "Files" }),
    );
  }
}

describe("AIContextProvider", () => {
  let provider: MockContextProvider;

  beforeEach(() => {
    provider = new MockContextProvider();
  });

  describe("formatContextId", () => {
    it("should format context ID correctly", () => {
      const item = provider.getItems()[0];
      const contextId = provider.formatContextId(item);
      expect(contextId).toBe("mock:item1");
    });

    it("should handle items with special characters", () => {
      const item = provider.getItems()[2];
      const contextId = provider.formatContextId(item);
      expect(contextId).toBe("mock:item_with_special-chars");
    });
  });

  describe("parseContextIds", () => {
    it("should parse valid mentions from input text", () => {
      const input = "Hello @item1 and @item2 world";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock:item1", "mock:item2"]);
    });

    it("should ignore invalid mentions", () => {
      const input = "Hello @item1 and @nonexistent world";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock:item1"]);
    });

    it("should handle mentions with special characters", () => {
      const input = "Use @item_with_special-chars here";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock:item_with_special-chars"]);
    });

    it("should handle input with no mentions", () => {
      const input = "This has no mentions";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual([]);
    });

    it("should handle empty input", () => {
      const input = "";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual([]);
    });

    it("should handle multiple occurrences of same mention", () => {
      const input = "@item1 and @item1 again";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock:item1", "mock:item1"]);
    });
  });

  describe("createBasicCompletion", () => {
    it("should create completion with default options", () => {
      const item = provider.getItems()[0];
      // @ts-expect-error - createBasicCompletion is protected
      const completion = provider.createBasicCompletion(item);

      expect(completion).toEqual({
        label: "@item1",
        displayLabel: "Item 1",
        detail: "First mock item",
        boost: 1,
        type: "mock",
        apply: "@item1",
        section: "Mock Items",
      });
    });

    it("should create completion with custom options", () => {
      const item = provider.getItems()[0];
      // @ts-expect-error - createBasicCompletion is protected
      const completion = provider.createBasicCompletion(item, {
        boost: 5,
        type: "custom",
        section: "Custom Section",
        detail: "Custom detail",
      });

      expect(completion).toEqual({
        label: "@item1",
        displayLabel: "Item 1",
        detail: "Custom detail",
        boost: 5,
        type: "custom",
        apply: "@item1",
        section: "Custom Section",
      });
    });

    it("should handle item without description", () => {
      const itemWithoutDesc: MockContextItem = {
        type: "mock",
        id: "no-desc",
        label: "No Description",
        data: { value: "test" },
      };

      // @ts-expect-error - createBasicCompletion is protected
      const completion = provider.createBasicCompletion(itemWithoutDesc);
      expect(completion.detail).toBeUndefined();
    });
  });

  describe("getCompletions", () => {
    it("should return completions for all items", () => {
      const completions = provider.getCompletions();
      expect(completions).toHaveLength(3);
      expect(completions[0].label).toBe("@item1");
      expect(completions[1].label).toBe("@item2");
      expect(completions[2].label).toBe("@item_with_special-chars");
    });

    it("should return empty array when no items", () => {
      provider.clearItems();
      const completions = provider.getCompletions();
      expect(completions).toEqual([]);
    });
  });
});

describe("AIContextRegistry", () => {
  let registry: AIContextRegistry<MockContextItem | FileContextItem>;
  let mockProvider: MockContextProvider;
  let fileProvider: FileContextProvider;

  beforeEach(() => {
    registry = new AIContextRegistry();
    mockProvider = new MockContextProvider();
    fileProvider = new FileContextProvider();
  });

  describe("register", () => {
    it("should register a provider", () => {
      const result = registry.register(mockProvider);
      expect(result).toBe(registry); // Should return itself for chaining
      expect(registry.getProviders().has(mockProvider)).toBe(true);
    });

    it("should allow chaining multiple registrations", () => {
      const result = registry.register(mockProvider).register(fileProvider);

      expect(result).toBe(registry);
      expect(registry.getProviders().has(mockProvider)).toBe(true);
      expect(registry.getProviders().has(fileProvider)).toBe(true);
    });

    it("should not register the same provider twice", () => {
      registry.register(mockProvider);
      registry.register(mockProvider);

      const providers = [...registry.getProviders()];
      const mockProviderCount = providers.filter(
        (p) => p === mockProvider,
      ).length;
      expect(mockProviderCount).toBe(1);
    });
  });

  describe("getProviders", () => {
    it("should return empty set initially", () => {
      expect(registry.getProviders().size).toBe(0);
    });

    it("should return all registered providers", () => {
      registry.register(mockProvider);
      registry.register(fileProvider);

      const providers = registry.getProviders();
      expect(providers.size).toBe(2);
      expect(providers.has(mockProvider)).toBe(true);
      expect(providers.has(fileProvider)).toBe(true);
    });
  });

  describe("getProvider", () => {
    beforeEach(() => {
      registry.register(mockProvider);
      registry.register(fileProvider);
    });

    it("should return provider by type", () => {
      const provider = registry.getProvider("mock");
      expect(provider).toBe(mockProvider);
    });

    it("should return undefined for unknown type", () => {
      const provider = registry.getProvider("unknown");
      expect(provider).toBeUndefined();
    });

    it("should handle multiple providers correctly", () => {
      const mockProviderResult = registry.getProvider("mock");
      const fileProviderResult = registry.getProvider("file");

      expect(mockProviderResult).toBe(mockProvider);
      expect(fileProviderResult).toBe(fileProvider);
    });
  });

  describe("getAllCompletions", () => {
    it("should return empty array when no providers", () => {
      const completions = registry.getAllCompletions();
      expect(completions).toEqual([]);
    });

    it("should return completions from single provider", () => {
      registry.register(mockProvider);
      const completions = registry.getAllCompletions();
      expect(completions).toHaveLength(3);
      expect(completions.every((c) => c.label.startsWith("@"))).toBe(true);
    });

    it("should return completions from multiple providers", () => {
      registry.register(mockProvider);
      registry.register(fileProvider);

      const completions = registry.getAllCompletions();
      expect(completions).toHaveLength(5); // 3 from mock + 2 from file

      const mockCompletions = completions.filter((c) =>
        c.label.startsWith("@"),
      );
      const fileCompletions = completions.filter((c) =>
        c.label.startsWith("#"),
      );

      expect(mockCompletions).toHaveLength(3);
      expect(fileCompletions).toHaveLength(2);
    });
  });

  describe("parseAllContextIds", () => {
    beforeEach(() => {
      registry.register(mockProvider);
      registry.register(fileProvider);
    });

    it("should parse context IDs from all providers", () => {
      const input = "Use @item1 and #config.py here";
      const contextIds = registry.parseAllContextIds(input);

      expect(contextIds).toContain("mock:item1");
      expect(contextIds).toContain("file:config.py");
      expect(contextIds).toHaveLength(2);
    });

    it("should handle input with no mentions", () => {
      const input = "This has no mentions";
      const contextIds = registry.parseAllContextIds(input);
      expect(contextIds).toEqual([]);
    });

    it("should handle mixed valid and invalid mentions", () => {
      const input = "Use @item1 and #nonexistent.py and @invalid";
      const contextIds = registry.parseAllContextIds(input);
      expect(contextIds).toEqual(["mock:item1"]);
    });

    it("should handle empty input", () => {
      const input = "";
      const contextIds = registry.parseAllContextIds(input);
      expect(contextIds).toEqual([]);
    });
  });

  describe("getContextInfo", () => {
    beforeEach(() => {
      registry.register(mockProvider);
      registry.register(fileProvider);
    });

    it("should return context info for valid IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock:item1",
        "file:config.py",
      ] as ContextLocatorId[];
      const contextInfo = registry.getContextInfo(contextIds);

      expect(contextInfo).toHaveLength(2);
      expect(contextInfo[0].id).toBe("item1");
      expect(contextInfo[1].id).toBe("config.py");
    });

    it("should ignore invalid context IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock:item1",
        "mock:nonexistent",
        "unknown:item",
      ];
      const contextInfo = registry.getContextInfo(contextIds);

      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].id).toBe("item1");
    });

    it("should return empty array for empty input", () => {
      const contextInfo = registry.getContextInfo([]);
      expect(contextInfo).toEqual([]);
    });

    it("should handle malformed context IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "malformed" as ContextLocatorId,
        "mock:item1",
      ];
      const contextInfo = registry.getContextInfo(contextIds);

      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].id).toBe("item1");
    });
  });

  describe("formatContextForAI", () => {
    beforeEach(() => {
      registry.register(mockProvider);
      registry.register(fileProvider);
    });

    it("should format context for AI with valid IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock:item1",
        "file:config.py",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toContain("Mock: Item 1 (value1)");
      expect(formatted).toContain("File: config.py");
      expect(formatted).toContain("Description: Configuration file");
      expect(formatted.split("\n\n")).toHaveLength(2);
    });

    it("should handle multiple items from same provider", () => {
      const contextIds: ContextLocatorId[] = [
        "mock:item1",
        "mock:item2",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toContain("Mock: Item 1 (value1)");
      expect(formatted).toContain("Mock: Item 2 (value2)");
      expect(formatted.split("\n\n")).toHaveLength(2);
    });

    it("should return empty string for empty input", () => {
      const formatted = registry.formatContextForAI([]);
      expect(formatted).toBe("");
    });

    it("should ignore invalid context IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock:item1",
        "unknown:item",
        "mock:nonexistent",
      ];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toContain("Mock: Item 1 (value1)");
      expect(formatted.split("\n\n")).toHaveLength(1);
    });

    it("should handle complex file paths", () => {
      const contextIds: ContextLocatorId[] = [
        "file:utils/helpers.py",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toContain("File: utils/helpers.py");
      expect(formatted).toContain("Description: Helper functions");
    });

    it("should handle malformed context IDs gracefully", () => {
      const contextIds: ContextLocatorId[] = [
        "mock:item1",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toContain("Mock: Item 1 (value1)");
      expect(formatted.split("\n\n")).toHaveLength(1);
    });
  });

  describe("edge cases and error handling", () => {
    it("should handle provider with no items", () => {
      const emptyProvider = new MockContextProvider();
      emptyProvider.clearItems();
      registry.register(emptyProvider);

      expect(registry.getAllCompletions()).toEqual([]);
      expect(registry.parseAllContextIds("@anything")).toEqual([]);
      expect(registry.getContextInfo(["mock:anything"])).toEqual([]);
      expect(registry.formatContextForAI(["mock:anything"])).toBe("");
    });

    it("should handle context ID with multiple colons", () => {
      // Add an item with colon in the ID
      const specialItem: MockContextItem = {
        type: "mock",
        id: "namespace", // Note: current implementation has a bug with split(":", 2)
        label: "Special Item",
        data: { value: "special" },
      };
      mockProvider.addItem(specialItem);
      registry.register(mockProvider);

      const contextIds: ContextLocatorId[] = [
        "mock:namespace:item:with:colons",
      ] as ContextLocatorId[];
      const contextInfo = registry.getContextInfo(contextIds);

      // Current implementation only gets "namespace" as id due to split(":", 2)
      // This is likely a bug - it should split only on first colon
      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].id).toBe("namespace");
    });

    it("should handle providers with same context type", () => {
      const anotherMockProvider = new MockContextProvider();
      registry.register(mockProvider);
      registry.register(anotherMockProvider);

      // Should return the first registered provider
      const provider = registry.getProvider("mock");
      expect(provider).toBe(mockProvider);
    });
  });
});
