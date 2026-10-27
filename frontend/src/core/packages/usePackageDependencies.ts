/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import { useResolvedMarimoConfig } from "@/core/config/config";
import { useRequestClient } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import { packageDataVersionAtom } from "./package-data";

/** Load the available package views and refresh them after package mutations. */
export function usePackageDependencies() {
  const packageDataVersion = useAtomValue(packageDataVersionAtom);
  const [config] = useResolvedMarimoConfig();
  const packageManager = config.package_management.manager;
  const { getDependencyTree, getPackageList } = useRequestClient();

  return useAsyncData(async () => {
    const { context, tree } = await getDependencyTree();
    // Both sandbox endpoints inspect the same environment; only fetch it once.
    const list =
      context.kind === "sandbox" ? [] : (await getPackageList()).packages;
    return { list, context, tree };
  }, [getDependencyTree, getPackageList, packageManager, packageDataVersion]);
}
