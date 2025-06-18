/* Copyright 2024 Marimo. All rights reserved. */

import { type UseQueryResult, useQuery } from "@tanstack/react-query";
import * as z from "zod";
import { cleanPythonModuleName, reverseSemverSort } from "@/utils/versions";

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

export function usePackageMetadata(
  packageName: string,
): UseQueryResult<PackageMetadata> {
  const cleanedName = cleanPythonModuleName(packageName);
  return useQuery({
    staleTime: 5 * 60 * 1000, // 5 minutes
    queryKey: ["usePackageMetadata", cleanedName],
    queryFn: async () => {
      const response = await fetch(
        `https://pypi.org/pypi/${cleanedName}/json`,
        { method: "GET" },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const pkgMeta = PyPiPackageResponse.parse(await response.json());
      return {
        versions: Object.keys(pkgMeta.releases).toSorted(reverseSemverSort),
        extras: pkgMeta.info.provides_extra ?? [],
      };
    },
  });
}
