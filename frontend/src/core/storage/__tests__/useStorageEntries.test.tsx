/* Copyright 2026 Marimo. All rights reserved. */

import { act, renderHook, waitFor } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type { ReactNode } from "react";
import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  storageAtom,
  useStorageEntries,
  useStoragePageFetcher,
} from "../state";
import type { StorageEntry, StorageState } from "../types";

const mockRequest = vi.fn();

vi.mock("../request-registry", () => ({
  ListStorageEntries: {
    request: (...args: unknown[]) => mockRequest(...args),
  },
}));

function makeEntry(
  overrides: Partial<StorageEntry> & { path: string },
): StorageEntry {
  return {
    kind: overrides.kind ?? "file",
    lastModified: overrides.lastModified ?? null,
    metadata: overrides.metadata ?? {},
    path: overrides.path,
    size: overrides.size ?? 0,
  };
}

describe("useStorageEntries", () => {
  let store: ReturnType<typeof createStore>;

  const wrapper = ({ children }: { children: ReactNode }) =>
    React.createElement(Provider, { store }, children);

  beforeEach(() => {
    vi.clearAllMocks();
    store = createStore();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function setStorageState(state: Partial<StorageState>) {
    const current = store.get(storageAtom);
    store.set(storageAtom, { ...current, ...state });
  }

  it("should fetch entries when not cached", async () => {
    const entries = [
      makeEntry({ path: "a.txt" }),
      makeEntry({ path: "b.txt" }),
    ];
    mockRequest.mockResolvedValue({ entries });

    const { result } = renderHook(() => useStorageEntries("my_s3", "data/"), {
      wrapper,
    });

    expect(result.current.isPending).toBe(true);
    expect(result.current.entries).toEqual([]);

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(result.current.entries).toEqual(entries);
    expect(mockRequest).toHaveBeenCalledWith({
      namespace: "my_s3",
      prefix: "data/",
      limit: 150,
    });
  });

  it("should return cached entries without fetching", async () => {
    const entries = [makeEntry({ path: "cached.txt" })];
    setStorageState({
      entriesByPath: new Map([["my_s3::data/", entries]]),
    });

    const { result } = renderHook(() => useStorageEntries("my_s3", "data/"), {
      wrapper,
    });

    expect(result.current.entries).toEqual(entries);
    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeUndefined();
    expect(mockRequest).not.toHaveBeenCalled();
  });

  it("should normalize null prefix to empty string", async () => {
    const entries = [makeEntry({ path: "root.txt" })];
    mockRequest.mockResolvedValue({ entries });

    const { result } = renderHook(() => useStorageEntries("ns"), { wrapper });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(result.current.entries).toEqual(entries);
    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ prefix: "" }),
    );
  });

  it("should normalize undefined prefix to empty string", async () => {
    const entries = [makeEntry({ path: "root.txt" })];
    mockRequest.mockResolvedValue({ entries });

    const { result } = renderHook(() => useStorageEntries("ns", undefined), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });

    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ prefix: "" }),
    );
  });

  it("should return the error when fetch fails and nothing is cached", async () => {
    mockRequest.mockRejectedValue(new Error("network failure"));

    const { result } = renderHook(() => useStorageEntries("ns", "pfx/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.error).toBeDefined();
    });

    expect(result.current.error?.message).toBe("network failure");
    expect(result.current.entries).toEqual([]);
    expect(result.current.isPending).toBe(false);
  });

  it("should surface result.error as a thrown error", async () => {
    mockRequest.mockResolvedValue({
      entries: [],
      error: "access denied",
    });

    const { result } = renderHook(() => useStorageEntries("ns", "pfx/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.error).toBeDefined();
    });

    expect(result.current.error?.message).toBe("access denied");
    expect(result.current.entries).toEqual([]);
    expect(result.current.isPending).toBe(false);
  });

  it("should suppress error when entries are cached", async () => {
    const entries = [makeEntry({ path: "ok.txt" })];
    setStorageState({
      entriesByPath: new Map([["ns::pfx/", entries]]),
    });

    const { result } = renderHook(() => useStorageEntries("ns", "pfx/"), {
      wrapper,
    });

    expect(result.current.error).toBeUndefined();
    expect(result.current.entries).toEqual(entries);
    expect(result.current.isPending).toBe(false);
  });

  it("should store fetched entries in the atom", async () => {
    const entries = [makeEntry({ path: "new.txt" })];
    mockRequest.mockResolvedValue({
      entries,
      next_page_token: "150",
    });

    renderHook(() => useStorageEntries("ns", "sub/"), { wrapper });

    await waitFor(() => {
      const state = store.get(storageAtom);
      expect(state.entriesByPath.get("ns::sub/")).toEqual(entries);
      expect(state.pageMetadataByPath.get("ns::sub/")?.nextPageToken).toBe(
        "150",
      );
    });
  });

  it("should load more entries when a next page token exists", async () => {
    const firstPage = [makeEntry({ path: "a.txt" })];
    const secondPage = [makeEntry({ path: "b.txt" })];
    mockRequest
      .mockResolvedValueOnce({
        entries: firstPage,
        next_page_token: "150",
      })
      .mockResolvedValueOnce({
        entries: secondPage,
        next_page_token: null,
      });

    const { result } = renderHook(() => useStorageEntries("ns", "sub/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.entries).toEqual(firstPage);
    });
    expect(result.current.hasMore).toBe(true);

    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.entries).toEqual([...firstPage, ...secondPage]);
    expect(result.current.hasMore).toBe(false);
    expect(mockRequest).toHaveBeenLastCalledWith({
      namespace: "ns",
      prefix: "sub/",
      limit: 150,
      pageToken: "150",
    });
  });

  it("should load more entries when the next page token is an empty string", async () => {
    const firstPage = [makeEntry({ path: "a.txt" })];
    const secondPage = [makeEntry({ path: "b.txt" })];
    mockRequest
      .mockResolvedValueOnce({
        entries: firstPage,
        next_page_token: "",
      })
      .mockResolvedValueOnce({
        entries: secondPage,
        next_page_token: null,
      });

    const { result } = renderHook(() => useStorageEntries("ns", "sub/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.entries).toEqual(firstPage);
    });
    expect(result.current.hasMore).toBe(true);

    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.entries).toEqual([...firstPage, ...secondPage]);
    expect(result.current.hasMore).toBe(false);
    expect(mockRequest).toHaveBeenLastCalledWith({
      namespace: "ns",
      prefix: "sub/",
      limit: 150,
      pageToken: "",
    });
  });

  it("should ignore duplicate load more calls while a page is loading", async () => {
    const firstPage = [makeEntry({ path: "a.txt" })];
    const secondPage = [makeEntry({ path: "b.txt" })];
    let resolveLoadMore!: (value: {
      entries: StorageEntry[];
      next_page_token: string | null;
    }) => void;
    const loadMorePromise = new Promise<{
      entries: StorageEntry[];
      next_page_token: string | null;
    }>((resolve) => {
      resolveLoadMore = resolve;
    });
    mockRequest
      .mockResolvedValueOnce({
        entries: firstPage,
        next_page_token: "150",
      })
      .mockReturnValueOnce(loadMorePromise);

    const { result } = renderHook(() => useStorageEntries("ns", "sub/"), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.entries).toEqual(firstPage);
    });

    await act(async () => {
      const firstLoad = result.current.loadMore();
      const secondLoad = result.current.loadMore();

      expect(mockRequest).toHaveBeenCalledTimes(2);
      resolveLoadMore({
        entries: secondPage,
        next_page_token: null,
      });
      await Promise.all([firstLoad, secondLoad]);
    });

    expect(result.current.entries).toEqual([...firstPage, ...secondPage]);
    expect(mockRequest).toHaveBeenCalledTimes(2);
  });

  it("should fetch arbitrary storage pages", async () => {
    const firstPage = [makeEntry({ path: "folder/a.txt" })];
    const secondPage = [makeEntry({ path: "folder/b.txt" })];
    mockRequest
      .mockResolvedValueOnce({
        entries: firstPage,
        next_page_token: "150",
      })
      .mockResolvedValueOnce({
        entries: secondPage,
        next_page_token: null,
      });

    const { result } = renderHook(() => useStoragePageFetcher(), {
      wrapper,
    });

    await act(async () => {
      await result.current({
        namespace: "ns",
        prefix: "folder/",
      });
    });
    await act(async () => {
      await result.current({
        namespace: "ns",
        prefix: "folder/",
        pageToken: "150",
        append: true,
      });
    });

    expect(store.get(storageAtom).entriesByPath.get("ns::folder/")).toEqual([
      ...firstPage,
      ...secondPage,
    ]);
    expect(mockRequest).toHaveBeenLastCalledWith({
      namespace: "ns",
      prefix: "folder/",
      limit: 150,
      pageToken: "150",
    });
  });

  it("should forward an empty string page token", async () => {
    mockRequest.mockResolvedValue({
      entries: [],
      next_page_token: null,
    });

    const { result } = renderHook(() => useStoragePageFetcher(), {
      wrapper,
    });

    await act(async () => {
      await result.current({
        namespace: "ns",
        prefix: "folder/",
        pageToken: "",
      });
    });

    expect(mockRequest).toHaveBeenLastCalledWith({
      namespace: "ns",
      prefix: "folder/",
      limit: 150,
      pageToken: "",
    });
  });
});
