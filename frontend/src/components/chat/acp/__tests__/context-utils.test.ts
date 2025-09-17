/* Copyright 2024 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, type Mocked, vi } from "vitest";
import {
  convertFilesToResourceLinks,
  parseContextFromPrompt,
} from "../context-utils";

// Mock dependencies
vi.mock("@/utils/fileToBase64", () => ({
  blobToString: vi.fn(),
}));

vi.mock("@/core/ai/context/context", () => ({
  getAIContextRegistry: vi.fn(),
}));

vi.mock("@/core/state/jotai", () => ({
  store: {},
}));

vi.mock("@/utils/Logger", () => ({
  Logger: {
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

import { getAIContextRegistry } from "@/core/ai/context/context";
import type {
  AIContextItem,
  AIContextRegistry,
  ContextLocatorId,
} from "@/core/ai/context/registry";
import { blobToString } from "@/utils/fileToBase64";

const CONTEXT_ID = "context1" as ContextLocatorId;

describe("convertFilesToResourceLinks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should convert files to resource links", async () => {
    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    vi.mocked(blobToString).mockResolvedValue(
      "data:text/plain;base64,Y29udGVudA==",
    );

    const result = await convertFilesToResourceLinks([mockFile]);

    expect(result).toEqual([
      {
        type: "resource_link",
        uri: "data:text/plain;base64,Y29udGVudA==",
        mimeType: "text/plain",
        name: "test.txt",
      },
    ]);
  });

  it("should handle empty file array", async () => {
    const result = await convertFilesToResourceLinks([]);
    expect(result).toEqual([]);
  });

  it("should handle file conversion errors gracefully", async () => {
    const mockFile = new File(["content"], "test.txt", { type: "text/plain" });
    vi.mocked(blobToString).mockRejectedValue(new Error("Conversion failed"));

    const result = await convertFilesToResourceLinks([mockFile]);

    expect(result).toEqual([]);
  });

  it("should process multiple files", async () => {
    const file1 = new File(["content1"], "test1.txt", { type: "text/plain" });
    const file2 = new File(["content2"], "test2.txt", { type: "text/plain" });

    vi.mocked(blobToString)
      .mockResolvedValueOnce("data:text/plain;base64,Y29udGVudDE=")
      .mockResolvedValueOnce("data:text/plain;base64,Y29udGVudDI=");

    const result = await convertFilesToResourceLinks([file1, file2]);

    expect(result).toHaveLength(2);
    expect((result[0] as { name: string }).name).toBe("test1.txt");
    expect((result[1] as { name: string }).name).toBe("test2.txt");
  });
});

describe("parseContextFromPrompt", () => {
  const mockRegistry = {
    parseAllContextIds: vi.fn(),
    formatContextForAI: vi.fn(),
    getAttachmentsForContext: vi.fn(),
  } as unknown as Mocked<AIContextRegistry<AIContextItem>>;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getAIContextRegistry).mockReturnValue(mockRegistry);
  });

  it("should return empty blocks when no @ symbol in prompt", async () => {
    const result = await parseContextFromPrompt("simple prompt");

    expect(result).toEqual({
      contextBlocks: [],
      attachmentBlocks: [],
    });
  });

  it("should return empty blocks when no context IDs found", async () => {
    mockRegistry.parseAllContextIds.mockReturnValue([]);

    const result = await parseContextFromPrompt("prompt with @ but no context");

    expect(result).toEqual({
      contextBlocks: [],
      attachmentBlocks: [],
    });
  });

  it("should create context blocks when context IDs are found", async () => {
    mockRegistry.parseAllContextIds.mockReturnValue([CONTEXT_ID]);
    mockRegistry.formatContextForAI.mockReturnValue("formatted context");
    mockRegistry.getAttachmentsForContext.mockResolvedValue([]);

    const result = await parseContextFromPrompt("prompt with @context1");

    expect(result.contextBlocks).toHaveLength(1);
    expect(result.contextBlocks[0]).toEqual({
      type: "resource",
      resource: {
        uri: "context.md",
        mimeType: "text/markdown",
        text: "formatted context",
      },
    });
    expect(result.attachmentBlocks).toHaveLength(0);
  });

  it("should create attachment blocks when attachments are found", async () => {
    mockRegistry.parseAllContextIds.mockReturnValue([CONTEXT_ID]);
    mockRegistry.formatContextForAI.mockReturnValue("formatted context");
    mockRegistry.getAttachmentsForContext.mockResolvedValue([
      {
        type: "file",
        url: "http://example.com/file.pdf",
        mediaType: "application/pdf",
        filename: "file.pdf",
      },
    ]);

    const result = await parseContextFromPrompt("prompt with @context1");

    expect(result.contextBlocks).toHaveLength(1);
    expect(result.attachmentBlocks).toHaveLength(1);
    expect(result.attachmentBlocks[0]).toEqual({
      type: "resource_link",
      uri: "http://example.com/file.pdf",
      mimeType: "application/pdf",
      name: "file.pdf",
    });
  });

  it("should handle empty context string gracefully", async () => {
    mockRegistry.parseAllContextIds.mockReturnValue([CONTEXT_ID]);
    mockRegistry.formatContextForAI.mockReturnValue("   ");
    mockRegistry.getAttachmentsForContext.mockResolvedValue([]);

    const result = await parseContextFromPrompt("prompt with @context1");

    expect(result.contextBlocks).toHaveLength(0);
    expect(result.attachmentBlocks).toHaveLength(0);
  });

  it("should handle registry errors gracefully", async () => {
    vi.mocked(getAIContextRegistry).mockImplementation(() => {
      throw new Error("Registry error");
    });

    const result = await parseContextFromPrompt("prompt with @context1");

    expect(result).toEqual({
      contextBlocks: [],
      attachmentBlocks: [],
    });
  });

  it("should handle attachment errors gracefully", async () => {
    mockRegistry.parseAllContextIds.mockReturnValue([CONTEXT_ID]);
    mockRegistry.formatContextForAI.mockReturnValue("formatted context");
    mockRegistry.getAttachmentsForContext.mockRejectedValue(
      new Error("Attachment error"),
    );

    const result = await parseContextFromPrompt("prompt with @context1");

    expect(result.contextBlocks).toHaveLength(1);
    expect(result.attachmentBlocks).toHaveLength(0);
  });

  it("should use url as name when filename is not provided", async () => {
    mockRegistry.parseAllContextIds.mockReturnValue([CONTEXT_ID]);
    mockRegistry.formatContextForAI.mockReturnValue("formatted context");
    mockRegistry.getAttachmentsForContext.mockResolvedValue([
      {
        type: "file",
        url: "http://example.com/file.pdf",
        mediaType: "application/pdf",
        filename: undefined,
      },
    ]);

    const result = await parseContextFromPrompt("prompt with @context1");

    expect((result.attachmentBlocks[0] as { name: string }).name).toBe(
      "http://example.com/file.pdf",
    );
  });
});
