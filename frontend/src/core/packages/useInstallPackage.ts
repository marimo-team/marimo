/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import { addPackage } from "@/core/network/requests";
import { Logger } from "@/utils/Logger";
import { showAddPackageToast } from "./toast-components";

export function useInstallPackages(): {
  handleInstallPackages: (
    packages: string[],
    onSuccess?: () => void,
  ) => Promise<void>;
  loading: boolean;
} {
  const [loading, setLoading] = useState(false);

  const handleInstallPackages = async (
    packages: string[],
    onSuccess?: () => void,
  ) => {
    setLoading(true);

    try {
      for (const [idx, packageName] of packages.entries()) {
        const response = await addPackage({ package: packageName });
        if (response.success) {
          showAddPackageToast(packageName);
        } else {
          showAddPackageToast(packageName, response.error);
        }
        // Wait 1s if there are more packages to install
        if (idx < packages.length - 1) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
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
