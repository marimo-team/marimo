/* Copyright 2026 Marimo. All rights reserved. */

import { useState } from "react";
import { Logger } from "@/utils/Logger";
import { useRequestClient } from "../network/requests";
import { showAddPackageToast } from "./toast-components";

export function useInstallPackages(): {
  handleInstallPackages: (
    packages: string[],
    onSuccess?: () => void,
  ) => Promise<void>;
  loading: boolean;
} {
  const [loading, setLoading] = useState(false);
  const { addPackage } = useRequestClient();

  const handleInstallPackages = async (
    packages: string[],
    onSuccess?: () => void,
  ) => {
    setLoading(true);

    try {
      // Batch all packages into a single install call.
      // The worker splits by space and passes the full list to micropip,
      // which resolves and downloads in parallel internally.
      const response = await addPackage({ package: packages.join(" ") });
      if (response.success) {
        for (const packageName of packages) {
          showAddPackageToast(packageName);
        }
      } else {
        for (const packageName of packages) {
          showAddPackageToast(packageName, response.error);
        }
      }
      onSuccess?.();
    } catch (error) {
      Logger.error(error);
    } finally {
      setLoading(false);
    }
  };

  return { loading, handleInstallPackages };
}
