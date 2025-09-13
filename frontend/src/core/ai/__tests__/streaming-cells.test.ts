/* Copyright 2024 Marimo. All rights reserved. */

import { renderHook } from "@testing-library/react";
import type { UIMessageChunk } from "ai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CellId } from "@/core/cells/ids";
import { useStagedCells } from "../staged-cells";

// Mock the dependencies
const mockCreateNewCell = vi.fn();
const mockUpdateCellCode = vi.fn();
const mockDeleteCellCallback = vi.fn();

vi.mock("../../cells/cells", () => ({
  useCellActions: () => ({
    createNewCell: mockCreateNewCell,
    updateCellCode: mockUpdateCellCode,
  }),
}));

vi.mock("@/components/editor/cell/useDeleteCell", () => ({
  useDeleteCellCallback: () => mockDeleteCellCallback,
}));

// Mock CellId.create
vi.mock("@/core/cells/ids", () => ({
  CellId: {
    create: vi.fn(),
  },
}));

describe("streaming functionality", () => {
  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();
  });

  describe("onStream function", () => {
    it("should handle text-start chunk by creating a new stream", () => {
      const { result } = renderHook(() => useStagedCells());

      const textStartChunk: UIMessageChunk = { type: "text-start", id: "1" };

      result.current.onStream(textStartChunk);

      // Stream should be created (we can't directly test the private property)
      // But we can test that it doesn't throw
      expect(() => result.current.onStream(textStartChunk)).not.toThrow();
    });

    it("should handle text-delta chunk when stream exists", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start the stream
      result.current.onStream({ type: "text-start", id: "1" });

      const textDeltaChunk: UIMessageChunk = {
        type: "text-delta",
        delta: "```python\nprint('hello')\n```",
        id: "1",
      };

      // Mock CellId.create to return a predictable ID
      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      result.current.onStream(textDeltaChunk);

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('hello')\n",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle text-delta chunk when stream doesn't exist", () => {
      const { result } = renderHook(() => useStagedCells());

      const textDeltaChunk: UIMessageChunk = {
        type: "text-delta",
        delta: "some text",
        id: "1",
      };

      // Should not throw but should log error
      expect(() => result.current.onStream(textDeltaChunk)).not.toThrow();
    });

    it("should handle text-end chunk by stopping the stream", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start the stream
      result.current.onStream({ type: "text-start", id: "1" });

      const textEndChunk: UIMessageChunk = { type: "text-end", id: "1" };

      expect(() => result.current.onStream(textEndChunk)).not.toThrow();
    });

    it("should handle text-end chunk when stream doesn't exist", () => {
      const { result } = renderHook(() => useStagedCells());

      const textEndChunk: UIMessageChunk = { type: "text-end", id: "1" };

      // Should not throw but should log error
      expect(() => result.current.onStream(textEndChunk)).not.toThrow();
    });

    it("should handle unknown chunk types", () => {
      const { result } = renderHook(() => useStagedCells());

      const unknownChunk = { type: "unknown", id: "1" };

      // Should not throw but should log error
      // @ts-expect-error - unknown chunk type
      expect(() => result.current.onStream(unknownChunk)).not.toThrow();
    });
  });

  describe("CellCreationStream stream method", () => {
    beforeEach(() => {
      // We need to access the CellCreationStream class for testing
      // Since it's not exported, we'll test it through the hook
    });

    it("should handle complete code block in single chunk", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send complete code block
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('hello world')\n```",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('hello world')\n",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle code block split across multiple chunks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send opening backticks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\n",
        id: "1",
      });

      // Verify cell was created with empty code
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "",
        before: false,
        newCellId: mockCellId,
      });

      // Send code content
      result.current.onStream({
        type: "text-delta",
        delta: "print('hello')\nprint('world')",
        id: "1",
      });

      // Verify cell was updated with the code content
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('hello')\nprint('world')",
        formattingChange: false,
      });

      // Send closing backticks
      result.current.onStream({
        type: "text-delta",
        delta: "\n```",
        id: "1",
      });

      // Verify final update with the complete code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('hello')\nprint('world')\n",
        formattingChange: false,
      });
    });

    it("should handle multiple code blocks in sequence", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId1 = "mock-cell-id-1" as CellId;
      const mockCellId2 = "mock-cell-id-2" as CellId;
      vi.mocked(CellId.create)
        .mockReturnValueOnce(mockCellId1)
        .mockReturnValueOnce(mockCellId2);

      // First code block
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('first')\n```",
        id: "1",
      });

      // Second code block
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('second')\n```",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledTimes(2);
      expect(mockCreateNewCell).toHaveBeenNthCalledWith(1, {
        cellId: "__end__",
        code: "print('first')\n",
        before: false,
        newCellId: mockCellId1,
      });
      expect(mockCreateNewCell).toHaveBeenNthCalledWith(2, {
        cellId: "__end__",
        code: "print('second')\n",
        before: false,
        newCellId: mockCellId2,
      });
    });

    it("should handle backticks within code content", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send code with backticks inside
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('`backtick` in code')\n```",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('`backtick` in code')\n",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle incomplete code block at end of stream", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send incomplete code block
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('incomplete')",
        id: "1",
      });

      // End stream
      result.current.onStream({ type: "text-end", id: "1" });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('incomplete')",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle text before code blocks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send text before code block
      result.current.onStream({
        type: "text-delta",
        delta: "Here's some code:\n```python\nprint('hello')\n```",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('hello')\n",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle text after code blocks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send code block followed by text
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('hello')\n```\nThat was the code.",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('hello')\n",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle multiple backticks (more than 3)", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send code with 5 backticks
      result.current.onStream({
        type: "text-delta",
        delta: "`````python\nprint('hello')\n`````",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('hello')\n",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle empty code blocks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send empty code block
      result.current.onStream({
        type: "text-delta",
        delta: "```python\n```",
        id: "1",
      });

      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "",
        before: false,
        newCellId: mockCellId,
      });
    });

    it("should handle no code blocks in stream", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      // Send text without code blocks
      result.current.onStream({
        type: "text-delta",
        delta: "This is just regular text without any code blocks.",
        id: "1",
      });

      // End stream
      result.current.onStream({ type: "text-end", id: "1" });

      // Should not create any cells
      expect(mockCreateNewCell).not.toHaveBeenCalled();
    });

    it("should call updateStagedCell with correct arguments for subsequent chunks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send opening backticks and initial code
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('initial')",
        id: "1",
      });

      // Verify cell was created
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('initial')",
        before: false,
        newCellId: mockCellId,
      });

      // Send additional code content
      result.current.onStream({
        type: "text-delta",
        delta: "\nprint('additional')",
        id: "1",
      });

      // Verify updateStagedCell was called with the updated code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('initial')\nprint('additional')",
        formattingChange: false,
      });

      // Send more code content
      result.current.onStream({
        type: "text-delta",
        delta: "\nprint('final')",
        id: "1",
      });

      // Verify updateStagedCell was called again with the complete code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('initial')\nprint('additional')\nprint('final')",
        formattingChange: false,
      });

      // Send closing backticks
      result.current.onStream({
        type: "text-delta",
        delta: "\n```",
        id: "1",
      });

      // Verify final update
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('initial')\nprint('additional')\nprint('final')\n",
        formattingChange: false,
      });
    });

    it("should handle multiple updates for a single code block", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send opening backticks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\n",
        id: "1",
      });

      // Send code in multiple small chunks
      const codeChunks = [
        "def hello():",
        "\n    print('Hello, world!')",
        "\n    return 'done'",
        "\nhello()",
      ];

      codeChunks.forEach((chunk, index) => {
        result.current.onStream({
          type: "text-delta",
          delta: chunk,
          id: "1",
        });

        // Verify updateStagedCell was called for each chunk
        const expectedCode = codeChunks.slice(0, index + 1).join("");
        expect(mockUpdateCellCode).toHaveBeenCalledWith({
          cellId: mockCellId,
          code: expectedCode,
          formattingChange: false,
        });
      });

      // Send closing backticks
      result.current.onStream({
        type: "text-delta",
        delta: "\n```",
        id: "1",
      });

      // Verify final update with complete code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "def hello():\n    print('Hello, world!')\n    return 'done'\nhello()\n",
        formattingChange: false,
      });
    });

    it("should handle updates with backticks in code content", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send opening backticks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\n",
        id: "1",
      });

      // Send code with backticks
      result.current.onStream({
        type: "text-delta",
        delta: "print('`backtick` in code')",
        id: "1",
      });

      // Verify updateStagedCell was called
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('`backtick` in code')",
        formattingChange: false,
      });

      // Send more code with more backticks
      result.current.onStream({
        type: "text-delta",
        delta: "\nprint('``double backticks``')",
        id: "1",
      });

      // Verify updateStagedCell was called with accumulated code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('`backtick` in code')\nprint('``double backticks``')",
        formattingChange: false,
      });
    });

    it("should handle updates for incomplete code blocks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send opening backticks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\n",
        id: "1",
      });

      // Send incomplete code
      result.current.onStream({
        type: "text-delta",
        delta: "print('incomplete code",
        id: "1",
      });

      // Verify updateStagedCell was called
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('incomplete code",
        formattingChange: false,
      });

      // End stream without closing backticks
      result.current.onStream({ type: "text-end", id: "1" });

      // Verify final update with incomplete code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "print('incomplete code",
        formattingChange: false,
      });
    });

    it("should handle updates with empty code blocks", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId = "mock-cell-id" as CellId;
      vi.mocked(CellId.create).mockReturnValue(mockCellId);

      // Send opening backticks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\n",
        id: "1",
      });

      // Send closing backticks immediately (empty code block)
      result.current.onStream({
        type: "text-delta",
        delta: "```",
        id: "1",
      });

      // Verify updateStagedCell was called with empty code
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId,
        code: "",
        formattingChange: false,
      });
    });

    it("should handle updates for multiple code blocks in sequence", () => {
      const { result } = renderHook(() => useStagedCells());

      // Start stream
      result.current.onStream({ type: "text-start", id: "1" });

      const mockCellId1 = "mock-cell-id-1" as CellId;
      const mockCellId2 = "mock-cell-id-2" as CellId;
      vi.mocked(CellId.create)
        .mockReturnValueOnce(mockCellId1)
        .mockReturnValueOnce(mockCellId2);

      // First code block - send in chunks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('first')",
        id: "1",
      });

      // Verify first cell was created
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('first')",
        before: false,
        newCellId: mockCellId1,
      });

      // Add more to first code block
      result.current.onStream({
        type: "text-delta",
        delta: "\nprint('first part 2')",
        id: "1",
      });

      // Verify updateStagedCell was called for first cell
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId1,
        code: "print('first')\nprint('first part 2')",
        formattingChange: false,
      });

      // Close first code block
      result.current.onStream({
        type: "text-delta",
        delta: "\n```",
        id: "1",
      });

      // Verify final update for first cell
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId1,
        code: "print('first')\nprint('first part 2')\n",
        formattingChange: false,
      });

      // Second code block - send in chunks
      result.current.onStream({
        type: "text-delta",
        delta: "```python\nprint('second')",
        id: "1",
      });

      // Verify second cell was created
      expect(mockCreateNewCell).toHaveBeenCalledWith({
        cellId: "__end__",
        code: "print('second')",
        before: false,
        newCellId: mockCellId2,
      });

      // Add more to second code block
      result.current.onStream({
        type: "text-delta",
        delta: "\nprint('second part 2')",
        id: "1",
      });

      // Verify updateStagedCell was called for second cell
      expect(mockUpdateCellCode).toHaveBeenCalledWith({
        cellId: mockCellId2,
        code: "print('second')\nprint('second part 2')",
        formattingChange: false,
      });
    });
  });
});
