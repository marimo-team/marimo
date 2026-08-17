/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  dataSourceDiscoveryEpochAtom,
  type DetectedDataSource,
  fetchDataSourceDiscovery,
} from "@/core/datasets/data-source-discovery";
import { useAsyncData } from "./useAsyncData";

/**
 * Reusable UI-facing hook for kernel-managed datasource discovery.
 * The kernel annotates sources that already have a matching connection.
 */
export function useDataSourceDiscovery() {
  const epoch = useAtomValue(dataSourceDiscoveryEpochAtom);
  return useAsyncData(fetchDataSourceDiscovery, [epoch]);
}

export type DataSourceDiscoveryGroup = "database" | "storage";

function matchesGroup(
  source: DetectedDataSource,
  group: DataSourceDiscoveryGroup | undefined,
): boolean {
  if (!group) {
    return true;
  }
  const isStorage = source.category === "object-storage";
  return isStorage === (group === "storage");
}

/**
 * Detected sources that aren't yet backed by an actual connection or storage
 * namespace, optionally narrowed to "database" (databases/catalogs) or
 * "storage" (object storage) suggestions.
 */
export function useUnconfiguredDataSources(
  group?: DataSourceDiscoveryGroup,
): DetectedDataSource[] {
  const { data } = useDataSourceDiscovery();

  if (!data) {
    return [];
  }
  return data.filter(
    (source) => matchesGroup(source, group) && !source.configured,
  );
}
