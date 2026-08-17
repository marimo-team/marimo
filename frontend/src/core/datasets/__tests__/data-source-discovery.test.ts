/* Copyright 2026 Marimo. All rights reserved. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectionAtom } from "@/core/network/connection";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import {
  fetchDataSourceDiscovery,
  invalidateDataSourceDiscovery,
  isDetectedSourceConnected,
  matchesDiscoveryGroup,
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

  it("returns sources from the kernel", async () => {
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
      },
    ];
    vi.spyOn(DiscoverDataSources, "request").mockResolvedValue({
      request_id: "request-id",
      sources,
    });

    await expect(fetchDataSourceDiscovery()).resolves.toEqual(sources);
  });
});

describe("matchesDiscoveryGroup", () => {
  const postgres: DetectedDataSource = {
    id: "postgres",
    integration: "postgres",
    category: "database",
    displayName: "PostgreSQL",
    confidence: "high",
    origins: [],
    configuration: [],
    code: "",
  };
  const iceberg: DetectedDataSource = {
    ...postgres,
    id: "iceberg",
    integration: "pyiceberg",
    category: "catalog",
    displayName: "PyIceberg",
  };
  const s3: DetectedDataSource = {
    ...postgres,
    id: "s3",
    integration: "aws",
    category: "object-storage",
    displayName: "S3",
  };

  it("keeps every source when no group is given", () => {
    expect(matchesDiscoveryGroup(postgres)).toBe(true);
    expect(matchesDiscoveryGroup(iceberg)).toBe(true);
    expect(matchesDiscoveryGroup(s3)).toBe(true);
  });

  it("groups catalogs with databases", () => {
    expect(matchesDiscoveryGroup(postgres, "database")).toBe(true);
    expect(matchesDiscoveryGroup(iceberg, "database")).toBe(true);
    expect(matchesDiscoveryGroup(s3, "database")).toBe(false);
  });

  it("narrows storage to object-storage sources", () => {
    expect(matchesDiscoveryGroup(postgres, "storage")).toBe(false);
    expect(matchesDiscoveryGroup(iceberg, "storage")).toBe(false);
    expect(matchesDiscoveryGroup(s3, "storage")).toBe(true);
  });
});

describe("isDetectedSourceConnected", () => {
  const postgres: DetectedDataSource = {
    id: "postgres",
    integration: "postgres",
    category: "database",
    displayName: "PostgreSQL",
    confidence: "high",
    origins: [],
    configuration: [],
    code: "",
  };
  const emptySnapshot = {
    dialects: [] as string[],
    storageProtocols: [] as string[],
    storageBackendTypes: [] as string[],
  };

  it("does not hide a source when nothing is connected", () => {
    expect(isDetectedSourceConnected(postgres, emptySnapshot)).toBe(false);
  });

  it("hides a database suggestion when a matching dialect is live", () => {
    expect(
      isDetectedSourceConnected(postgres, {
        ...emptySnapshot,
        dialects: ["postgresql"],
      }),
    ).toBe(true);
  });

  it("does not hide a database suggestion for a different dialect", () => {
    expect(
      isDetectedSourceConnected(postgres, {
        ...emptySnapshot,
        dialects: ["mysql", "duckdb"],
      }),
    ).toBe(false);
  });

  it("hides spark suggestions for either pyspark or spark dialects", () => {
    const spark: DetectedDataSource = {
      ...postgres,
      id: "spark",
      integration: "pyspark",
      category: "catalog",
      displayName: "Spark",
    };
    expect(
      isDetectedSourceConnected(spark, {
        ...emptySnapshot,
        dialects: ["spark"],
      }),
    ).toBe(true);
  });

  it("hides object storage when a matching protocol is live", () => {
    const s3: DetectedDataSource = {
      ...postgres,
      id: "s3",
      integration: "aws",
      category: "object-storage",
      displayName: "S3",
    };
    expect(
      isDetectedSourceConnected(s3, {
        ...emptySnapshot,
        storageProtocols: ["s3"],
      }),
    ).toBe(true);
  });

  it("hides huggingface when the backend type matches", () => {
    const hf: DetectedDataSource = {
      ...postgres,
      id: "hf",
      integration: "huggingface",
      category: "object-storage",
      displayName: "Hugging Face",
    };
    expect(
      isDetectedSourceConnected(hf, {
        ...emptySnapshot,
        storageBackendTypes: ["huggingface"],
      }),
    ).toBe(true);
  });

  it("does not hide unknown integrations", () => {
    expect(
      isDetectedSourceConnected(
        { ...postgres, integration: "custom" },
        { ...emptySnapshot, dialects: ["custom"] },
      ),
    ).toBe(false);
  });
});
