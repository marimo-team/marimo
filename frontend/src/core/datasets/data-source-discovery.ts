/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { components } from "@marimo-team/marimo-api";
import { waitForConnectionOpenIfNotebook } from "../network/connection";
import { store } from "../state/jotai";
import { storageNamespacesAtom } from "../storage/state";
import { dataConnectionsMapAtom } from "./data-source-connections";
import { DiscoverDataSources } from "./request-registry";

export type DetectedDataSource = components["schemas"]["DetectedDataSource"];

/**
 * Bumped when discovery should be re-fetched (kernel restart, new connection, etc.).
 */
export const dataSourceDiscoveryEpochAtom = atom(0);

/**
 * Kernel-managed datasource discovery scans the environment once per epoch.
 * The kernel annotates each source with whether it already has a matching
 * connection or storage namespace. Every consumer shares a single in-flight
 * request per epoch.
 */
let discoveryPromise: Promise<DetectedDataSource[]> | undefined;
let discoveryEpoch = 0;
let discoveryNamespaceKey: string | undefined;

function sortedUnique(values: string[]): string[] {
  return [...new Set(values)].toSorted();
}

function getDiscoveryNamespace() {
  const connections = store.get(dataConnectionsMapAtom);
  const storageNamespaces = store.get(storageNamespacesAtom);
  return {
    dialects: sortedUnique(
      [...connections.values()].map((connection) =>
        connection.dialect.toLowerCase(),
      ),
    ),
    storageProtocols: sortedUnique(
      storageNamespaces.map((namespace) => namespace.protocol),
    ),
    storageBackendTypes: sortedUnique(
      storageNamespaces.map((namespace) => namespace.backendType),
    ),
  };
}

export function fetchDataSourceDiscovery(): Promise<DetectedDataSource[]> {
  const epoch = store.get(dataSourceDiscoveryEpochAtom);
  if (!discoveryPromise || discoveryEpoch !== epoch) {
    discoveryEpoch = epoch;
    discoveryPromise = waitForConnectionOpenIfNotebook()
      .then(() => {
        const namespace = getDiscoveryNamespace();
        discoveryNamespaceKey = JSON.stringify(namespace);
        return DiscoverDataSources.request(namespace);
      })
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
  discoveryNamespaceKey = undefined;
  store.set(dataSourceDiscoveryEpochAtom, (value) => value + 1);
}

/**
 * Refetches only when the live connection/storage metadata has changed.
 */
export function invalidateDataSourceDiscoveryIfNamespaceChanged(): void {
  const namespaceKey = JSON.stringify(getDiscoveryNamespace());
  if (namespaceKey !== discoveryNamespaceKey) {
    invalidateDataSourceDiscovery();
  }
}
