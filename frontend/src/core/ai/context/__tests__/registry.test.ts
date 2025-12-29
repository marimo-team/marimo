/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { FileUIPart } from "ai";
import { createStore } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { notebookAtom } from "@/core/cells/cells";
import { CellId as CellIdClass } from "@/core/cells/ids";
import {
  type ErrorContextItem,
  ErrorContextProvider,
} from "../providers/error";
import {
  type AIContextItem,
  AIContextProvider,
  AIContextRegistry,
  type ContextLocatorId,
} from "../registry";

// Mock context item for testing
interface MockContextItem extends AIContextItem {
  type: "mock" | "attachment";
  data: {
    value: string;
    needsAttachment?: boolean;
  };
}

// Mock attachment data for testing
const mockAttachment1: FileUIPart = {
  type: "file",
  filename: "test-image-1.png",
  mediaType: "image/png",
  url: "data:image/png;base64,mockdata1",
};

const mockAttachment2: FileUIPart = {
  type: "file",
  filename: "test-image-2.jpg",
  mediaType: "image/jpeg",
  url: "data:image/jpeg;base64,mockdata2",
};

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

  // Method to add items for testing
  addItem(item: MockContextItem): void {
    this.items.push(item);
  }

  // Method to clear items for testing
  clearItems(): void {
    this.items = [];
  }
}

// Test provider that supports attachments
class AttachmentContextProvider extends AIContextProvider<MockContextItem> {
  readonly title = "Attachment Items";
  readonly mentionPrefix = "@";
  readonly contextType = "attachment";

  private items: MockContextItem[];
  private attachments: FileUIPart[];

  constructor(items: MockContextItem[] = [], attachments: FileUIPart[] = []) {
    super();
    this.items = items;
    this.attachments = attachments;
  }

  getItems(): MockContextItem[] {
    return this.items;
  }

  formatContext(item: MockContextItem): string {
    return `Attachment: ${item.name} (${item.data.value})`;
  }

  formatCompletion(item: MockContextItem): Completion {
    return this.createBasicCompletion(item);
  }

  override async getAttachments(
    items: MockContextItem[],
  ): Promise<FileUIPart[]> {
    // Return attachments for items that need them
    const itemsNeedingAttachments = items.filter(
      (item) => item.data.needsAttachment,
    );
    return itemsNeedingAttachments
      .map((_, index) => this.attachments[index % this.attachments.length])
      .filter(Boolean);
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

  describe("Integration with ErrorContextProvider", () => {
    let errorProvider: ErrorContextProvider;
    let store: ReturnType<typeof createStore>;
    let registry: AIContextRegistry<ErrorContextItem>;

    beforeEach(() => {
      store = createStore();

      // Create mock notebook with errors using the new MockNotebook utilities
      const cellId1 = CellIdClass.create();
      const cellId2 = CellIdClass.create();

      const notebookState = MockNotebook.notebookStateWithErrors([
        {
          cellId: cellId1,
          cellName: "Cell 1",
          errorData: [
            MockNotebook.errors.syntax("Invalid syntax"),
            MockNotebook.errors.exception("Runtime error"),
          ],
        },
        {
          cellId: cellId2,
          cellName: "Cell 2",
          errorData: [MockNotebook.errors.cycle()],
        },
      ]);

      store.set(notebookAtom, notebookState);
      errorProvider = new ErrorContextProvider(store);
      registry = new AIContextRegistry<ErrorContextItem>().register(
        errorProvider,
      );
    });

    it("should register and provide error context items", () => {
      const provider = registry.getProvider("error");
      expect(provider).toBe(errorProvider);

      const items = registry.getAllItems();
      expect(items).toHaveLength(1);
      expect(items[0].type).toBe("error");
      expect(items[0].name).toBe("Errors");
    });

    it("should parse error context IDs correctly", () => {
      const contextIds = registry.parseAllContextIds(
        "Use @error://all to analyze errors",
      );
      expect(contextIds).toEqual(["error://all"]);

      const contextInfo = registry.getContextInfo(contextIds);
      expect(contextInfo).toHaveLength(1);
      expect(contextInfo[0].type).toBe("error");
    });

    it("should format error context for AI", () => {
      const contextIds = ["error://all"] as ContextLocatorId[];
      const formattedContext = registry.formatContextForAI(contextIds);

      expect(formattedContext).toContain("<error");
      expect(formattedContext).toContain("Cell 1");
      expect(formattedContext).toContain("Cell 2");
      expect(formattedContext).toContain("Invalid syntax");
      expect(formattedContext).toContain("This cell is in a cycle");
    });

    it("should provide error completions", () => {
      // Get the error provider and test its completion directly
      const provider = registry.getProvider("error");
      expect(provider).toBeDefined();

      const items = provider!.getItems();
      expect(items).toHaveLength(1);

      const completion = provider!.formatCompletion(items[0]);
      expect(completion.label).toBe("@Errors");
      expect(completion.type).toBe("error");
    });

    it("should handle empty errors gracefully", () => {
      // Create store with no errors using MockNotebook
      const emptyStore = createStore();
      const emptyNotebookState = MockNotebook.notebookStateWithErrors([]);
      emptyStore.set(notebookAtom, emptyNotebookState);

      const emptyErrorProvider = new ErrorContextProvider(emptyStore);
      const emptyRegistry = new AIContextRegistry().register(
        emptyErrorProvider,
      );

      const items = emptyRegistry.getAllItems();
      expect(items).toHaveLength(0);
    });

    it("should work with mixed providers", () => {
      const mixedRegistry = new AIContextRegistry<
        ErrorContextItem | MockContextItem
      >()
        .register(errorProvider)
        .register(mockProvider);

      const items = mixedRegistry.getAllItems();
      expect(items.length).toBeGreaterThan(1);

      // Should have both error and mock items
      const errorItems = items.filter((item) => item.type === "error");
      const mockItems = items.filter((item) => item.type === "mock");

      expect(errorItems).toHaveLength(1);
      expect(mockItems).toHaveLength(3);
    });

    it("should parse mixed context IDs", () => {
      const mixedRegistry = new AIContextRegistry<
        ErrorContextItem | MockContextItem
      >()
        .register(errorProvider)
        .register(mockProvider);

      const input = "Use @error://all and @mock://item1 for analysis";
      const contextIds = mixedRegistry.parseAllContextIds(input);

      expect(contextIds).toContain("error://all");
      expect(contextIds).toContain("mock://item1");
      expect(contextIds).toHaveLength(2);
    });

    it("should format mixed context for AI", () => {
      const mixedRegistry = new AIContextRegistry<
        ErrorContextItem | MockContextItem
      >()
        .register(errorProvider)
        .register(mockProvider);

      const contextIds = ["error://all", "mock://item1"] as ContextLocatorId[];
      const formattedContext = mixedRegistry.formatContextForAI(contextIds);

      // Should contain both error and mock context
      expect(formattedContext).toContain("<error");
      expect(formattedContext).toContain("Mock:");
      expect(formattedContext).toContain("Cell 1");
      expect(formattedContext).toContain("Item 1");
    });
  });

  describe("attachment functionality", () => {
    let attachmentProvider: AttachmentContextProvider;
    let attachmentRegistry: AIContextRegistry<MockContextItem>;

    beforeEach(() => {
      const itemWithAttachment: MockContextItem = {
        uri: "attachment://item1" as ContextLocatorId,
        name: "item1",
        type: "attachment",
        description: "Item with attachment",
        data: { needsAttachment: true, value: "test1" },
      };

      const itemWithoutAttachment: MockContextItem = {
        uri: "attachment://item2" as ContextLocatorId,
        name: "item2",
        type: "attachment",
        description: "Item without attachment",
        data: { needsAttachment: false, value: "test2" },
      };

      attachmentProvider = new AttachmentContextProvider(
        [itemWithAttachment, itemWithoutAttachment],
        [mockAttachment1, mockAttachment2],
      );

      attachmentRegistry = new AIContextRegistry<MockContextItem>().register(
        attachmentProvider,
      );
    });

    describe("getAttachmentsForContext", () => {
      it("should return empty array for empty context IDs", async () => {
        const attachments = await attachmentRegistry.getAttachmentsForContext(
          [],
        );
        expect(attachments).toEqual([]);
      });

      it("should return empty array for non-existent context IDs", async () => {
        const nonExistentIds = ["attachment://nonexistent" as ContextLocatorId];
        const attachments =
          await attachmentRegistry.getAttachmentsForContext(nonExistentIds);
        expect(attachments).toEqual([]);
      });

      it("should get attachments from provider that supports them", async () => {
        const contextIds = ["attachment://item1" as ContextLocatorId];
        const attachments =
          await attachmentRegistry.getAttachmentsForContext(contextIds);

        expect(attachments).toHaveLength(1);
        expect(attachments[0]).toEqual(mockAttachment1);
      });

      it("should not get attachments for items that don't need them", async () => {
        const contextIds = ["attachment://item2" as ContextLocatorId];
        const attachments =
          await attachmentRegistry.getAttachmentsForContext(contextIds);

        expect(attachments).toHaveLength(0);
      });

      it("should not get attachments from providers with default implementation", async () => {
        const simpleRegistry =
          new AIContextRegistry<MockContextItem>().register(mockProvider);

        const contextIds = ["mock://item1" as ContextLocatorId];
        const attachments =
          await simpleRegistry.getAttachmentsForContext(contextIds);

        expect(attachments).toHaveLength(0);
      });

      it("should handle multiple context IDs from different providers", async () => {
        const mixedRegistry = new AIContextRegistry<MockContextItem>()
          .register(attachmentProvider)
          .register(mockProvider);

        const contextIds = [
          "attachment://item1" as ContextLocatorId, // should have attachment
          "attachment://item2" as ContextLocatorId, // should not have attachment
          "mock://item1" as ContextLocatorId, // provider doesn't support attachments
        ];

        const attachments =
          await mixedRegistry.getAttachmentsForContext(contextIds);

        // Only attachment://item1 should contribute an attachment
        expect(attachments).toHaveLength(1);
        expect(attachments[0]).toEqual(mockAttachment1);
      });

      it("should handle multiple items needing attachments", async () => {
        const multiItem1: MockContextItem = {
          uri: "attachment://multi1" as ContextLocatorId,
          name: "multi1",
          type: "attachment",
          description: "Multi item 1",
          data: { needsAttachment: true, value: "multi1" },
        };

        const multiItem2: MockContextItem = {
          uri: "attachment://multi2" as ContextLocatorId,
          name: "multi2",
          type: "attachment",
          description: "Multi item 2",
          data: { needsAttachment: true, value: "multi2" },
        };

        const multiProvider = new AttachmentContextProvider(
          [multiItem1, multiItem2],
          [mockAttachment1, mockAttachment2],
        );

        const multiRegistry = new AIContextRegistry<MockContextItem>().register(
          multiProvider,
        );

        const contextIds = [
          "attachment://multi1" as ContextLocatorId,
          "attachment://multi2" as ContextLocatorId,
        ];

        const attachments =
          await multiRegistry.getAttachmentsForContext(contextIds);

        expect(attachments).toHaveLength(2);
        expect(attachments).toContainEqual(mockAttachment1);
        expect(attachments).toContainEqual(mockAttachment2);
      });

      it("should handle provider errors gracefully", async () => {
        const errorProvider = new AttachmentContextProvider([
          {
            uri: "attachment://error-item" as ContextLocatorId,
            name: "error-item",
            type: "attachment",
            description: "Item that causes error",
            data: { needsAttachment: true, value: "error" },
          },
        ]);

        // Override getAttachments to throw an error
        errorProvider.getAttachments = vi
          .fn()
          .mockRejectedValue(new Error("Attachment error"));

        const errorRegistry = new AIContextRegistry<MockContextItem>()
          .register(errorProvider)
          .register(mockProvider);

        const contextIds = [
          "attachment://error-item" as ContextLocatorId,
          "mock://item1" as ContextLocatorId,
        ];

        // Should not throw and should handle the error gracefully
        const attachments =
          await errorRegistry.getAttachmentsForContext(contextIds);
        expect(attachments).toEqual([]);
      });
    });

    describe("provider batching for attachments", () => {
      it("should batch multiple items to the same provider", async () => {
        const getAttachmentsSpy = vi.spyOn(
          attachmentProvider,
          "getAttachments",
        );

        const contextIds = [
          "attachment://item1" as ContextLocatorId,
          "attachment://item2" as ContextLocatorId,
        ];

        await attachmentRegistry.getAttachmentsForContext(contextIds);

        // Should call getAttachments once with both items
        expect(getAttachmentsSpy).toHaveBeenCalledTimes(1);
        expect(getAttachmentsSpy).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({ uri: "attachment://item1" }),
            expect.objectContaining({ uri: "attachment://item2" }),
          ]),
        );
      });

      it("should call different providers separately", async () => {
        const mixedRegistry = new AIContextRegistry<MockContextItem>()
          .register(attachmentProvider)
          .register(mockProvider);

        const attachmentSpy = vi.spyOn(attachmentProvider, "getAttachments");
        const mockSpy = vi.spyOn(mockProvider, "getAttachments");

        const contextIds = [
          "attachment://item1" as ContextLocatorId,
          "mock://item1" as ContextLocatorId,
        ];

        await mixedRegistry.getAttachmentsForContext(contextIds);

        // Should call each provider once
        expect(attachmentSpy).toHaveBeenCalledTimes(1);
        expect(mockSpy).toHaveBeenCalledTimes(1);

        expect(attachmentSpy).toHaveBeenCalledWith([
          expect.objectContaining({ uri: "attachment://item1" }),
        ]);
        expect(mockSpy).toHaveBeenCalledWith([
          expect.objectContaining({ uri: "mock://item1" }),
        ]);
      });
    });
  });
});
