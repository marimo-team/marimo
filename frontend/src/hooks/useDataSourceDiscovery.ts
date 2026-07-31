/* Copyright 2026 Marimo. All rights reserved. */

import type { DetectedDataSource } from "@/core/datasets/data-source-discovery";
import { DiscoverDataSources } from "@/core/datasets/request-registry";
import { useAsyncData } from "./useAsyncData";

export async function loadDataSourceDiscovery(): Promise<DetectedDataSource[]> {
  const result = await DiscoverDataSources.request({});
  return result.sources;
}

/**
 * Reusable UI-facing hook for kernel-managed datasource discovery.
 * Consumers decide how to render, filter, or act on the detected model.
 */
export function useDataSourceDiscovery() {
  return useAsyncData(loadDataSourceDiscovery, []);
}
