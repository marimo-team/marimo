/* Copyright 2026 Marimo. All rights reserved. */
import type { components } from "@marimo-team/marimo-api";

export type StorageEntry = components["schemas"]["StorageEntry"];
export type StorageNamespace = components["schemas"]["StorageNamespace"];

/**
 * Key for looking up lazy-loaded entries: "namespace::prefix"
 */
export type StoragePathKey = `${string}::${string}`;

export const STORAGE_PATH_SEPARATOR = "::";

export function storagePathKey(
  namespace: string,
  prefix: string | null | undefined,
): StoragePathKey {
  return `${namespace}${STORAGE_PATH_SEPARATOR}${prefix ?? ""}`;
}

export function storageNamespacePrefix(namespace: string): string {
  return `${namespace}${STORAGE_PATH_SEPARATOR}`;
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

export function storageUrl(
  protocol: string,
  rootPath: string,
  entryPath: string,
): URL {
  const parts = [rootPath, entryPath].filter(Boolean);
  const path = parts.join("/").replaceAll(/\/+/g, "/");
  return new URL(`${protocol}://${path}`);
}

export const ROOT_PATH = "";
export const DEFAULT_FETCH_LIMIT = 150;

/** Non-exhaustive list of known storage protocols */
export type KnownStorageProtocol =
  | "s3"
  | "gcs"
  | "azure"
  | "coreweave"
  | "cloudflare"
  | "http"
  | "file"
  | "in-memory";
