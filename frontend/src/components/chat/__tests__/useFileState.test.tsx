/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockModules } from "@/__mocks__/common";
import { toast } from "@/components/ui/use-toast";
import { convertToFileUIPart, useFileState } from "../chat-utils";

vi.mock("@/components/ui/use-toast", () => MockModules.toast());

describe("useFileState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initializes with no files", () => {
    const { result } = renderHook(() => useFileState());
    expect(result.current.files).toEqual([]);
  });

  it("adds files when under size limit", async () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    await act(() => result.current.addFiles([fileA, fileB]));

    expect(result.current.files).toEqual([fileA, fileB]);
    expect(toast).not.toHaveBeenCalled();
  });

  it("appends new files to existing files", async () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    await act(() => result.current.addFiles([fileA]));
    await act(() => result.current.addFiles([fileB]));

    expect(result.current.files).toEqual([fileA, fileB]);
  });

  it("ignores empty file list", async () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;

    await act(() => result.current.addFiles([fileA]));
    await act(() => result.current.addFiles([]));

    expect(result.current.files).toEqual([fileA]);
  });

  it("shows toast and skips adding when size exceeds limit", async () => {
    const { result } = renderHook(() => useFileState());
    const bigFile = {
      name: "big.txt",
      size: 1024 * 1024 * 50 + 1, // > 50MB
    } as File;

    await act(() => result.current.addFiles([bigFile]));

    expect(result.current.files).toEqual([]);
    expect(toast).toHaveBeenCalledWith({
      title: "File size exceeded",
      description: "Attachments must be under 50 MB",
      variant: "danger",
    });
  });

  it("removes a file", async () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    await act(() => result.current.addFiles([fileA, fileB]));
    act(() => result.current.removeFile(fileA));

    expect(result.current.files).toEqual([fileB]);
  });

  it("clears all files", async () => {
    const { result } = renderHook(() => useFileState());
    const fileA = { name: "a.txt", size: 10 } as File;
    const fileB = { name: "b.txt", size: 20 } as File;

    await act(() => result.current.addFiles([fileA, fileB]));
    expect(result.current.files).toEqual([fileA, fileB]);

    act(() => result.current.clearFiles());
    expect(result.current.files).toEqual([]);
  });

  it("rejects files outside the selected model's input types", async () => {
    const { result } = renderHook(() => useFileState(["text/*"]));
    const image = new File(["image"], "chart.png", { type: "image/png" });

    await act(() => result.current.addFiles([image]));

    expect(result.current.files).toEqual([]);
    expect(toast).toHaveBeenCalledWith({
      title: "Unsupported attachment",
      description:
        "These files are not supported by the selected model: chart.png",
      variant: "danger",
    });
  });

  it.each([
    ["application/toml", "pyproject.toml"],
    ["application/xml", "data.xml"],
    ["application/x-yaml", "config.yml"],
    ["application/vnd.example+json", "data.json"],
    ["application/javascript", "script.js"],
    ["application/x-ndjson", "data.ndjson"],
    ["", "script.py"],
    ["application/octet-stream", "config.yaml"],
    ["", "README"],
    ["application/octet-stream", "file.unlisted-extension"],
  ])("accepts and serializes textual files: %s, %s", async (type, name) => {
    const { result } = renderHook(() => useFileState(["text/*"]));
    const file = new File(["hello"], name, { type });

    await act(() => result.current.addFiles([file]));

    expect(
      result.current.files.map((file) => ({
        name: file.name,
        type: file.type,
      })),
    ).toEqual([{ name, type: "text/plain" }]);
    expect(await convertToFileUIPart(result.current.files)).toEqual([
      {
        type: "file",
        mediaType: "text/plain",
        filename: name,
        url: "data:text/plain;base64,aGVsbG8=",
      },
    ]);
    expect(toast).not.toHaveBeenCalled();
  });

  it("revalidates pending files after switching models without losing them", async () => {
    const { result, rerender } = renderHook(
      ({ types }) => useFileState(types),
      { initialProps: { types: ["text/*", "image/png"] } },
    );
    const image = new File(["image"], "chart.png", { type: "image/png" });
    await act(() => result.current.addFiles([image]));

    rerender({ types: ["text/*"] });

    expect(result.current.validateFiles(result.current.files)).toBe(false);
    expect(result.current.files).toEqual([image]);
  });

  it("rejects binary files with missing MIME metadata", async () => {
    const { result } = renderHook(() => useFileState(["text/*"]));
    const file = new File([new Uint8Array([0, 255])], "README");

    await act(() => result.current.addFiles([file]));

    expect(result.current.files).toEqual([]);
    expect(toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Unsupported attachment" }),
    );
  });

  it("discards pending reads when files are cleared", async () => {
    const { result } = renderHook(() => useFileState(["text/*"]));
    const file = new File(["hello"], "README");
    const read = Promise.withResolvers<ArrayBuffer>();
    vi.spyOn(file, "arrayBuffer").mockReturnValue(read.promise);
    const adding = result.current.addFiles([file]);

    act(() => result.current.clearFiles());
    await act(async () => {
      read.resolve(new TextEncoder().encode("hello").buffer);
      await adding;
    });

    expect(result.current.files).toEqual([]);
    expect(toast).not.toHaveBeenCalled();
  });
});
