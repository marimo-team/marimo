/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "@/components/ui/use-toast";
import { useFileState } from "../chat-utils";

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

describe("useFileState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initializes with no files", () => {
    const { result } = renderHook(() => useFileState());
    expect(result.current.files).toEqual([]);
  });

  it("adds files when under size limit", () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    act(() => result.current.addFiles([fileA, fileB]));

    expect(result.current.files).toEqual([fileA, fileB]);
    expect(toast).not.toHaveBeenCalled();
  });

  it("appends new files to existing files", () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    act(() => result.current.addFiles([fileA]));
    act(() => result.current.addFiles([fileB]));

    expect(result.current.files).toEqual([fileA, fileB]);
  });

  it("ignores empty file list", () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;

    act(() => result.current.addFiles([fileA]));
    act(() => result.current.addFiles([]));

    expect(result.current.files).toEqual([fileA]);
  });

  it("shows toast and skips adding when size exceeds limit", () => {
    const { result } = renderHook(() => useFileState());
    const bigFile = {
      name: "big.txt",
      size: 1024 * 1024 * 50 + 1, // > 50MB
    } as File;

    act(() => result.current.addFiles([bigFile]));

    expect(result.current.files).toEqual([]);
    expect(toast).toHaveBeenCalledWith({
      title: "File size exceeded",
      description: "Attachments must be under 50 MB",
      variant: "danger",
    });
  });

  it("removes a file", () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    act(() => result.current.addFiles([fileA, fileB]));
    act(() => result.current.removeFile(fileA));

    expect(result.current.files).toEqual([fileB]);
  });

  it("clears all files", () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    act(() => result.current.addFiles([fileA, fileB]));
    expect(result.current.files).toEqual([fileA, fileB]);

    act(() => result.current.clearFiles());
    expect(result.current.files).toEqual([]);
  });
});
