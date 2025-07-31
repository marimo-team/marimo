/* Copyright 2024 Marimo. All rights reserved. */

import { foldAll, unfoldAll } from "@codemirror/language";
import type { EditorView } from "@codemirror/view";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { foldAllBulk, makeBulkCommand, unfoldAllBulk } from "../commands";

vi.mock("@codemirror/language", () => ({
  foldAll: vi.fn(),
  unfoldAll: vi.fn(),
}));

describe("makeBulkCommand", () => {
  it("should return false for empty array", () => {
    const mockCommand = vi.fn().mockReturnValue(true);
    const bulkCommand = makeBulkCommand(mockCommand);

    const result = bulkCommand([]);

    expect(result).toBe(false);
    expect(mockCommand).not.toHaveBeenCalled();
  });

  it("should skip null targets", () => {
    const mockCommand = vi.fn().mockReturnValue(true);
    const bulkCommand = makeBulkCommand(mockCommand);

    const result = bulkCommand([null, null]);

    expect(result).toBe(false);
    expect(mockCommand).not.toHaveBeenCalled();
  });

  it("should apply command to non-null targets", () => {
    const mockCommand = vi.fn().mockReturnValue(true);
    const bulkCommand = makeBulkCommand(mockCommand);
    const view1 = { dispatch: vi.fn() } as unknown as EditorView;
    const view2 = { dispatch: vi.fn() } as unknown as EditorView;

    const result = bulkCommand([view1, null, view2]);

    expect(result).toBe(true);
    expect(mockCommand).toHaveBeenCalledTimes(2);
    expect(mockCommand).toHaveBeenCalledWith(view1);
    expect(mockCommand).toHaveBeenCalledWith(view2);
  });

  it("should return true if any command returns true", () => {
    const mockCommand = vi
      .fn()
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);
    const bulkCommand = makeBulkCommand(mockCommand);
    const view1 = { dispatch: vi.fn() } as unknown as EditorView;
    const view2 = { dispatch: vi.fn() } as unknown as EditorView;

    const result = bulkCommand([view1, view2]);

    expect(result).toBe(true);
    expect(mockCommand).toHaveBeenCalledTimes(2);
  });

  it("should return false if all commands return false", () => {
    const mockCommand = vi.fn().mockReturnValue(false);
    const bulkCommand = makeBulkCommand(mockCommand);
    const view1 = { dispatch: vi.fn() } as unknown as EditorView;
    const view2 = { dispatch: vi.fn() } as unknown as EditorView;

    const result = bulkCommand([view1, view2]);

    expect(result).toBe(false);
    expect(mockCommand).toHaveBeenCalledTimes(2);
  });
});

describe("foldAllBulk and unfoldAllBulk", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should apply foldAll to all targets", () => {
    const view1 = { dispatch: vi.fn() } as unknown as EditorView;
    const view2 = { dispatch: vi.fn() } as unknown as EditorView;
    vi.mocked(foldAll).mockReturnValue(true);

    const result = foldAllBulk([view1, view2]);

    expect(result).toBe(true);
    expect(foldAll).toHaveBeenCalledTimes(2);
    expect(foldAll).toHaveBeenCalledWith(view1);
    expect(foldAll).toHaveBeenCalledWith(view2);
  });

  it("should apply unfoldAll to all targets", () => {
    const view1 = { dispatch: vi.fn() } as unknown as EditorView;
    const view2 = { dispatch: vi.fn() } as unknown as EditorView;
    vi.mocked(unfoldAll).mockReturnValue(true);

    const result = unfoldAllBulk([view1, view2]);

    expect(result).toBe(true);
    expect(unfoldAll).toHaveBeenCalledTimes(2);
    expect(unfoldAll).toHaveBeenCalledWith(view1);
    expect(unfoldAll).toHaveBeenCalledWith(view2);
  });
});
