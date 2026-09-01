/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { components } from "@marimo-team/marimo-api";
import { waitForConnectionOpenIfNotebook } from "../network/connection";
import { store } from "../state/jotai";
import { DiscoverDataSources } from "./request-registry";

export type DetectedDataSource = components["schemas"]["DetectedDataSource"];

export type DataSourceDiscoveryGroup = "database" | "storage";

/** Category filter for UI surfaces. Catalogs ride with databases. */
export function matchesDiscoveryGroup(
  source: DetectedDataSource,
  group?: DataSourceDiscoveryGroup,
): boolean {
  if (!group) {
    return true;
  }
  const isStorage = source.category === "object-storage";
  return isStorage === (group === "storage");
}

/**
 * Live engines and storage used to hide suggestions of the same type.
 */
export interface LiveConnectionSnapshot {
  dialects: readonly string[];
  storageProtocols: readonly string[];
  storageBackendTypes: readonly string[];
}

/**
 * Whether a detected source already has a live connection of the same type.
 * Match rules come from the kernel on each suggestion.
 */
export function isDetectedSourceConnected(
  source: DetectedDataSource,
  snapshot: LiveConnectionSnapshot,
): boolean {
  const match = source.hidesWhen;
  if (match.kind === "dialect") {
    return match.substrings.some((alias) =>
      snapshot.dialects.some((dialect) => dialect.includes(alias)),
    );
  }

  if (
    match.protocols.some((protocol) =>
      snapshot.storageProtocols.includes(protocol),
    )
  ) {
    return true;
  }

  return match.backendTypes.some((backendType) =>
    snapshot.storageBackendTypes.includes(backendType),
  );
}

/**
 * Bumped when discovery should be re-fetched (kernel restart).
 */
export const dataSourceDiscoveryEpochAtom = atom(0);

/**
 * Kernel-managed datasource discovery scans the environment once per epoch.
 * Every consumer shares a single in-flight request.
 */
let discoveryPromise: Promise<DetectedDataSource[]> | undefined;
let discoveryEpoch = 0;

export function fetchDataSourceDiscovery(): Promise<DetectedDataSource[]> {
  const epoch = store.get(dataSourceDiscoveryEpochAtom);
  if (!discoveryPromise || discoveryEpoch !== epoch) {
    discoveryEpoch = epoch;
    discoveryPromise = waitForConnectionOpenIfNotebook()
      .then(() => DiscoverDataSources.request({}))
      .then((result) => result.sources)
      .catch((error: unknown) => {
        if (discoveryEpoch === epoch) {
          discoveryPromise = undefined;
        }
        throw error;
      });
  }
  return discoveryPromise;
}

/**
 * Clears the shared discovery cache and triggers consumers to refetch.
 */
export function invalidateDataSourceDiscovery(): void {
  discoveryPromise = undefined;
  store.set(dataSourceDiscoveryEpochAtom, (value) => value + 1);
}
