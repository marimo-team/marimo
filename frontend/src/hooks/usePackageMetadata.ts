/* Copyright 2024 Marimo. All rights reserved. */

import * as z from "zod";
import { TimedCache } from "@/utils/timed-cache";
import { cleanPythonModuleName, reverseSemverSort } from "@/utils/versions";
import { type AsyncDataResult, useAsyncData } from "./useAsyncData";

interface PackageMetadata {
  versions: string[];
  extras: string[];
}

const PACKAGE_CACHE = new TimedCache<PackageMetadata>({
  ttl: 5 * 60 * 1000, // 5 minutes
});

export type PyPiPackageResponse = z.infer<typeof PyPiPackageResponse>;

const PyPiPackageResponse = z.object({
  info: z.object({
    provides_extra: z.string().array().nullable(),
  }),
  releases: z.record(z.string(), z.unknown()),
});

export function usePackageMetadata(
  packageName: string,
): AsyncDataResult<PackageMetadata> {
  const cleanedName = cleanPythonModuleName(packageName);
  return useAsyncData(async () => {
    const cached = PACKAGE_CACHE.get(cleanedName);
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

    PACKAGE_CACHE.set(cleanedName, pkgMeta);
    return pkgMeta;
  }, [cleanedName]);
}
