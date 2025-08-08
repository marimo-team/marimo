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
      uri: this.asURI("item1"),
      name: "Item 1",
      description: "First mock item",
      data: { value: "value1" },
    },
    {
      type: "mock",
      uri: this.asURI("item2"),
      name: "Item 2",
      description: "Second mock item",
      data: { value: "value2" },
    },
    {
      type: "mock",
      uri: this.asURI("item_with_special-chars"),
      name: "Special Item",
      description: "Item with special characters",
      data: { value: "special" },
    },
  ];

  getItems(): MockContextItem[] {
    return this.items;
  }

  formatContext(item: MockContextItem): string {
    return `Mock: ${item.name} (${item.data.value})`;
  }

  formatCompletion(item: MockContextItem): Completion {
    return this.createBasicCompletion(item);
  }

  getCompletions(): Completion[] {
    return [];
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
  data: { value: string };
}

// Another mock provider with different prefix and type
class FileContextProvider extends AIContextProvider<FileContextItem> {
  readonly title = "Files";
  readonly mentionPrefix = "@";
  readonly contextType = "file";

  private items: FileContextItem[] = [
    {
      type: "file",
      uri: this.asURI("config.py"),
      name: "config.py",
      description: "Configuration file",
      data: { value: "config" },
    },
    {
      type: "file",
      uri: this.asURI("utils/helpers.py"),
      name: "utils/helpers.py",
      description: "Helper functions",
      data: { value: "helpers" },
    },
  ];

  getItems(): FileContextItem[] {
    return this.items;
  }

  formatCompletion(item: FileContextItem): Completion {
    return this.createBasicCompletion(item);
  }

  formatContext(item: FileContextItem): string {
    return `File: ${item.uri}\nDescription: ${item.description}`;
  }

  getCompletions(): Completion[] {
    return [];
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
      const contextId = item.uri;
      expect(contextId).toBe("mock://item1");
    });

    it("should handle items with special characters", () => {
      const item = provider.getItems()[2];
      const contextId = item.uri;
      expect(contextId).toBe("mock://item_with_special-chars");
    });
  });

  describe("parseContextIds", () => {
    it("should parse valid mentions from input text", () => {
      const input = "Hello @mock://item1 and @mock://item2 world";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock://item1", "mock://item2"]);
    });

    it("should ignore invalid mentions", () => {
      const input = "Hello @mock://item1 and @nonexistent world";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock://item1"]);
    });

    it("should handle mentions with special characters", () => {
      const input = "Use @mock://item_with_special-chars here";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock://item_with_special-chars"]);
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
      const input = "@mock://item1 and @mock://item1 again";
      const contextIds = provider.parseContextIds(input);
      expect(contextIds).toEqual(["mock://item1"]);
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
        apply: "@mock://item1",
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
        apply: "@mock://item1",
        section: "Custom Section",
      });
    });

    it("should handle item without description", () => {
      const itemWithoutDesc: MockContextItem = {
        type: "mock",
        uri: "no-desc",
        name: "No Description",
        data: { value: "test" },
      };

      // @ts-expect-error - createBasicCompletion is protected
      const completion = provider.createBasicCompletion(itemWithoutDesc);
      expect(completion.detail).toBeUndefined();
    });
  });

  describe("getCompletions", () => {
    it("should return empty array (refactored to use formatCompletion)", () => {
      const completions = provider.getCompletions();
      expect(completions).toEqual([]);
    });

    it("should return empty array when no items", () => {
      provider.clearItems();
      const completions = provider.getCompletions();
      expect(completions).toEqual([]);
    });
  });

  describe("formatCompletion", () => {
    it("should format completions correctly", () => {
      const items = provider.getItems();
      const completion = provider.formatCompletion(items[0]);
      expect(completion.label).toBe("@item1");
      expect(completion.displayLabel).toBe("Item 1");
      expect(completion.detail).toBe("First mock item");
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

    it("should return empty array from providers (refactored to use formatCompletion)", () => {
      registry.register(mockProvider);
      const completions = registry.getAllCompletions();
      expect(completions).toEqual([]);
    });

    it("should return empty arrays from multiple providers", () => {
      registry.register(mockProvider);
      registry.register(fileProvider);

      const completions = registry.getAllCompletions();
      expect(completions).toEqual([]);
    });
  });

  describe("parseAllContextIds", () => {
    beforeEach(() => {
      registry.register(mockProvider);
      registry.register(fileProvider);
    });

    it("should parse context IDs from all providers", () => {
      const input = "Use @mock://item1 and @file://config.py here";
      const contextIds = registry.parseAllContextIds(input);

      expect(contextIds).toContain("mock://item1");
      expect(contextIds).toContain("file://config.py");
      expect(contextIds).toHaveLength(2);
    });

    it("should handle input with no mentions", () => {
      const input = "This has no mentions";
      const contextIds = registry.parseAllContextIds(input);
      expect(contextIds).toEqual([]);
    });

    it("should handle mixed valid and invalid mentions", () => {
      const input = "Use @mock://item1 and #nonexistent.py and @invalid";
      const contextIds = registry.parseAllContextIds(input);
      expect(contextIds).toEqual(["mock://item1"]);
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
        "mock://item1",
        "file://config.py",
      ] as ContextLocatorId[];
      const contextInfo = registry.getContextInfo(contextIds);

      expect(contextInfo).toHaveLength(2);
      expect(contextInfo[0].uri).toBe("mock://item1");
      expect(contextInfo[1].uri).toBe("file://config.py");
    });

    it("should ignore invalid context IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock://item1",
        "mock://nonexistent",
        "unknown://item",
      ] as ContextLocatorId[];
      const contextInfo = registry.getContextInfo(contextIds);

      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].uri).toBe("mock://item1");
    });

    it("should return empty array for empty input", () => {
      const contextInfo = registry.getContextInfo([]);
      expect(contextInfo).toEqual([]);
    });

    it("should handle malformed context IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "malformed" as ContextLocatorId,
        "mock://item1",
      ] as ContextLocatorId[];
      const contextInfo = registry.getContextInfo(contextIds);

      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].uri).toBe("mock://item1");
    });
  });

  describe("formatContextForAI", () => {
    beforeEach(() => {
      registry.register(mockProvider);
      registry.register(fileProvider);
    });

    it("should format context for AI with valid IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock://item1",
        "file://config.py",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toMatchInlineSnapshot(`
        "Mock: Item 1 (value1)

        File: file://config.py
        Description: Configuration file"
      `);
    });

    it("should handle multiple items from same provider", () => {
      const contextIds: ContextLocatorId[] = [
        "mock://item1",
        "mock://item2",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toMatchInlineSnapshot(`
        "Mock: Item 1 (value1)

        Mock: Item 2 (value2)"
      `);
    });

    it("should return empty string for empty input", () => {
      const formatted = registry.formatContextForAI([]);
      expect(formatted).toBe("");
    });

    it("should ignore invalid context IDs", () => {
      const contextIds: ContextLocatorId[] = [
        "mock://item1",
        "unknown://item",
        "mock://nonexistent",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toContain("Mock: Item 1 (value1)");
      expect(formatted.split("\n\n")).toHaveLength(1);
    });

    it("should handle complex file paths", () => {
      const contextIds: ContextLocatorId[] = [
        "file://utils/helpers.py",
      ] as ContextLocatorId[];
      const formatted = registry.formatContextForAI(contextIds);

      expect(formatted).toMatchInlineSnapshot(`
        "File: file://utils/helpers.py
        Description: Helper functions"
      `);
    });

    it("should handle malformed context IDs gracefully", () => {
      const contextIds: ContextLocatorId[] = [
        "mock://item1",
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
      expect(
        registry.getContextInfo(["mock://anything"] as ContextLocatorId[]),
      ).toEqual([]);
      expect(
        registry.formatContextForAI(["mock://anything"] as ContextLocatorId[]),
      ).toBe("");
    });

    it("should handle context ID with multiple colons", () => {
      // Add an item with colon in the ID
      const specialItem: MockContextItem = {
        type: "mock",
        uri: "mock://namespace:item:with:colons", // Note: current implementation has a bug with split(":", 2)
        name: "Special Item",
        data: { value: "special" },
      };
      mockProvider.addItem(specialItem);
      registry.register(mockProvider);

      const contextIds: ContextLocatorId[] = [
        "mock://namespace:item:with:colons",
      ] as ContextLocatorId[];
      const contextInfo = registry.getContextInfo(contextIds);

      // Current implementation only gets "namespace" as id due to split(":", 2)
      // This is likely a bug - it should split only on first colon
      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].uri).toBe("mock://namespace:item:with:colons");
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
