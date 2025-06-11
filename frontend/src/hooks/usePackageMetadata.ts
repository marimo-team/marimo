/* Copyright 2024 Marimo. All rights reserved. */

import { useAsyncData } from "./useAsyncData";
import { cleanPythonModuleName, reverseSemverSort } from "@/utils/versions";
import * as z from "zod";

interface PackageMetadata {
  versions: string[];
  extras: string[];
}

export type PyPiPackageResponse = z.infer<typeof PyPiPackageResponse>;

const PyPiPackageResponse = z.object({
  info: z.object({
    provides_extra: z.string().array().nullable(),
  }),
  releases: z.record(z.string(), z.unknown()),
});

const packageCache = new Map<
  string,
  { data: PackageMetadata; timestamp: number }
>();
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

function getCachedData(
  normalizedPackageName: string,
): PackageMetadata | undefined {
  // cleanup expired entries
  {
    const now = Date.now();
    for (const [key, cached] of packageCache.entries()) {
      if (now - cached.timestamp > CACHE_DURATION) {
        packageCache.delete(key);
      }
    }
  }

  const cached = packageCache.get(normalizedPackageName);
  if (!cached) {
    return undefined;
  }

  const now = Date.now();
  if (now - cached.timestamp > CACHE_DURATION) {
    packageCache.delete(normalizedPackageName);
    return undefined;
  }

  return cached.data;
}

function setCachedData(
  normalizedPackageName: string,
  data: PackageMetadata,
): void {
  packageCache.set(normalizedPackageName, {
    data,
    timestamp: Date.now(),
  });
}

interface LoadingResponse {
  loading: true;
  data: undefined;
  error: undefined;
}

interface ErrorResponse {
  loading: false;
  data: undefined;
  error: Error;
}

interface SuccessResponse<T> {
  loading: false;
  data: T;
  error: undefined;
}

type AsyncDataResponse<T> =
  | LoadingResponse
  | ErrorResponse
  | SuccessResponse<T>;

export function usePackageMetadata(
  packageName: string,
): AsyncDataResponse<PackageMetadata> {
  const cleanedName = cleanPythonModuleName(packageName);

  const { data, loading, error } = useAsyncData(async () => {
    const cached = getCachedData(cleanedName);
    if (cached) {
      return cached;
    }

    const response = await fetch(`https://pypi.org/pypi/${cleanedName}/json`, {
      method: "GET",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const pkgMeta = PyPiPackageResponse.transform((meta) => ({
      versions: Object.keys(meta.releases).toSorted(reverseSemverSort),
      extras: meta.info.provides_extra ?? [],
    })).parse(await response.json());

    setCachedData(cleanedName, pkgMeta);
    return pkgMeta;
  }, [cleanedName]);

  return { data, loading, error } as AsyncDataResponse<PackageMetadata>;
}
