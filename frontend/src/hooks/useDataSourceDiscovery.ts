/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { dataConnectionsMapAtom } from "@/core/datasets/data-source-connections";
import {
  dataSourceDiscoveryEpochAtom,
  type DataSourceDiscoveryGroup,
  type DetectedDataSource,
  fetchDataSourceDiscovery,
  isDetectedSourceConnected,
  matchesDiscoveryGroup,
} from "@/core/datasets/data-source-discovery";
import { storageNamespacesAtom } from "@/core/storage/state";
import { useAsyncData } from "./useAsyncData";

/**
 * Reusable UI-facing hook for kernel-managed datasource discovery.
 */
export function useDataSourceDiscovery() {
  const epoch = useAtomValue(dataSourceDiscoveryEpochAtom);
  return useAsyncData(fetchDataSourceDiscovery, [epoch]);
}

/**
 * Detected sources from the kernel environment that are not already backed
 * by a live connection, optionally narrowed to "database" or "storage".
 */
export function useDetectedDataSources(
  group?: DataSourceDiscoveryGroup,
): DetectedDataSource[] {
  const { data } = useDataSourceDiscovery();
  const connections = useAtomValue(dataConnectionsMapAtom);
  const storageNamespaces = useAtomValue(storageNamespacesAtom);

  return useMemo(() => {
    if (!data) {
      return [];
    }

    const snapshot = {
      dialects: [...connections.values()].map((connection) =>
        connection.dialect.toLowerCase(),
      ),
      storageProtocols: storageNamespaces.map((namespace) =>
        namespace.protocol.toLowerCase(),
      ),
      storageBackendTypes: storageNamespaces.map((namespace) =>
        namespace.backendType.toLowerCase(),
      ),
    };

    return data.filter(
      (source) =>
        matchesDiscoveryGroup(source, group) &&
        !isDetectedSourceConnected(source, snapshot),
    );
  }, [connections, data, group, storageNamespaces]);
}
