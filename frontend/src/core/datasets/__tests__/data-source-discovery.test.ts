/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectionAtom } from "@/core/network/connection";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import {
  fetchDataSourceDiscovery,
  invalidateDataSourceDiscovery,
  type DetectedDataSource,
} from "../data-source-discovery";
import { DiscoverDataSources } from "../request-registry";

describe("fetchDataSourceDiscovery", () => {
  beforeEach(() => {
    // Discovery waits for the session's websocket connection to be open
    // before requesting, so it doesn't race a still-connecting session.
    store.set(connectionAtom, { state: WebSocketState.OPEN });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    invalidateDataSourceDiscovery();
  });

  it("shares a single in-flight request across concurrent callers", async () => {
    const request = vi
      .spyOn(DiscoverDataSources, "request")
      .mockResolvedValue({ request_id: "request-id", sources: [] });

    await Promise.all([
      fetchDataSourceDiscovery(),
      fetchDataSourceDiscovery(),
      fetchDataSourceDiscovery(),
    ]);

    expect(request).toHaveBeenCalledTimes(1);
  });

  it("re-runs discovery after the cache is invalidated", async () => {
    const request = vi
      .spyOn(DiscoverDataSources, "request")
      .mockResolvedValue({ request_id: "request-id", sources: [] });

    await fetchDataSourceDiscovery();
    invalidateDataSourceDiscovery();
    await fetchDataSourceDiscovery();

    expect(request).toHaveBeenCalledTimes(2);
  });

  it("clears the cache on failure so the next call retries", async () => {
    const request = vi
      .spyOn(DiscoverDataSources, "request")
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({ request_id: "request-id", sources: [] });

    await expect(fetchDataSourceDiscovery()).rejects.toThrow("boom");
    await expect(fetchDataSourceDiscovery()).resolves.toEqual([]);
    expect(request).toHaveBeenCalledTimes(2);
  });

  it("does not clear a newer cache entry when an invalidated request fails", async () => {
    let rejectFirstRequest: ((error: Error) => void) | undefined;
    const firstRequest = new Promise<{
      request_id: string;
      sources: DetectedDataSource[];
    }>((_resolve, reject) => {
      rejectFirstRequest = reject;
    });
    const request = vi
      .spyOn(DiscoverDataSources, "request")
      .mockReturnValueOnce(firstRequest)
      .mockResolvedValueOnce({ request_id: "request-id", sources: [] });

    const staleResult = fetchDataSourceDiscovery().catch((error) => error);
    await vi.waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    invalidateDataSourceDiscovery();
    await fetchDataSourceDiscovery();

    rejectFirstRequest?.(new Error("stale request failed"));
    await staleResult;
    await fetchDataSourceDiscovery();

    expect(request).toHaveBeenCalledTimes(2);
  });

  it("returns sources annotated by the kernel", async () => {
    const sources: DetectedDataSource[] = [
      {
        id: "postgres",
        integration: "postgres",
        category: "database",
        displayName: "PostgreSQL",
        confidence: "high",
        origins: [],
        configuration: [],
        code: "",
        configured: true,
      },
      {
        id: "mysql",
        integration: "mysql",
        category: "database",
        displayName: "MySQL",
        confidence: "high",
        origins: [],
        configuration: [],
        code: "",
        configured: false,
      },
    ];
    vi.spyOn(DiscoverDataSources, "request").mockResolvedValue({
      request_id: "request-id",
      sources,
    });

    await expect(fetchDataSourceDiscovery()).resolves.toEqual(sources);
  });
});
