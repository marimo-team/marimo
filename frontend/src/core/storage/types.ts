/* Copyright 2026 Marimo. All rights reserved. */
import type { components } from "@marimo-team/marimo-api";

export type StorageEntry = components["schemas"]["StorageEntry"];
export type StorageNamespace = components["schemas"]["StorageNamespace"];

/**
 * Key for looking up lazy-loaded entries: "namespace::prefix"
 */
export type StoragePathKey = `${string}::${string}`;

export function storagePathKey(
  namespace: string,
  prefix: string | null | undefined,
): StoragePathKey {
  return `${namespace}::${prefix ?? ""}`;
}

/**
 * The storage state.
 */
export interface StorageState {
  /** Namespaces from the broadcast notification */
  namespaces: StorageNamespace[];
  /** Lazy-loaded entries keyed by "namespace::prefix" */
  entriesByPath: ReadonlyMap<StoragePathKey, StorageEntry[]>;
}

export const DEFAULT_FETCH_LIMIT = 150;

/** Non-exhaustive list of known storage protocols */
export type KnownStorageProtocol =
  | "s3"
  | "gcs"
  | "azure"
  | "http"
  | "file"
  | "in-memory";

export const CLOUD_PROTOCOLS: ReadonlySet<KnownStorageProtocol> = new Set([
  "s3",
  "gcs",
  "azure",
  "http",
]);

export const LOCAL_PROTOCOLS: ReadonlySet<KnownStorageProtocol> = new Set([
  "file",
  "in-memory",
]);
