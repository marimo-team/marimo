/* Copyright 2026 Marimo. All rights reserved. */

import type { CompletionContext } from "@codemirror/autocomplete";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { EditRequests, FileInfo, RunRequests } from "@/core/network/types";
import { FileContextProvider } from "../file";

describe("FileContextProvider", () => {
  let provider: FileContextProvider;
  let mockApiRequests: Partial<EditRequests & RunRequests>;

  beforeEach(() => {
    mockApiRequests = {
      sendSearchFiles: vi.fn(),
    };
    provider = new FileContextProvider(
      mockApiRequests as EditRequests & RunRequests,
    );
  });

  it("should have correct provider properties", () => {
    expect(provider.title).toBe("Files");
    expect(provider.mentionPrefix).toBe("#");
    expect(provider.contextType).toBe("file");
  });

  it("should return empty items array for static getItems", () => {
    expect(provider.getItems()).toEqual([]);
  });

  it("should format context item correctly", () => {
    const item = {
      uri: provider.asURI("/path/to/file.py"),
      name: "file.py",
      type: "file" as const,
      description: "Python file",
      data: {
        path: "/path/to/file.py",
        isDirectory: false,
        isMarimoFile: false,
      },
    };

    const context = provider.formatContext(item);
    expect(context).toContain("file");
    expect(context).toContain("file.py");
    expect(context).toContain("/path/to/file.py");
  });

  it("should create completion source that returns null for no match", async () => {
    const completionSource = provider.createCompletionSource();
    const mockContext = {
      matchBefore: vi.fn().mockReturnValue(null),
    } as unknown as CompletionContext;

    const result = await completionSource(mockContext);
    expect(result).toBeNull();
  });

  it("should create completion source that searches files for matches", async () => {
    const mockFiles: FileInfo[] = [
      {
        id: "1",
        path: "/src/app.py",
        name: "app.py",
        isDirectory: false,
        isMarimoFile: false,
        lastModified: Date.now(),
      },
      {
        id: "2",
        path: "/src/utils",
        name: "utils",
        isDirectory: true,
        isMarimoFile: false,
        lastModified: Date.now(),
      },
    ];

    vi.mocked(mockApiRequests.sendSearchFiles!).mockResolvedValue({
      files: mockFiles,
      query: "app",
      totalFound: 2,
    });

    const completionSource = provider.createCompletionSource();
    const mockContext = {
      matchBefore: vi.fn().mockReturnValue({
        text: "#app",
        from: 0,
      }),
    } as unknown as CompletionContext;

    const result = await completionSource(mockContext);

    expect(result).not.toBeNull();
    expect(result!.from).toBe(0);
    expect(result!.options).toHaveLength(2);
    expect(result!.options[0].label).toContain("app.py");
    expect(result!.options[0].displayLabel).toContain("app.py");
  });

  it("should handle search errors gracefully", async () => {
    vi.mocked(mockApiRequests.sendSearchFiles!).mockRejectedValue(
      new Error("Search failed"),
    );

    const completionSource = provider.createCompletionSource();
    const mockContext = {
      matchBefore: vi.fn().mockReturnValue({
        text: "#test",
        from: 0,
      }),
    } as unknown as CompletionContext;

    const result = await completionSource(mockContext);
    expect(result).toBeNull();
  });
});
