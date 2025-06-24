/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import { addPackage } from "@/core/network/requests";
import { showAddPackageToast } from "./toast-components";

export function useInstallPackages(): {
  handleInstallPackages: (
    packages: string[],
    onSuccess?: () => void,
  ) => Promise<void>;
  loading: boolean;
  error: string | null;
  success: boolean;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleInstallPackages = async (
    packages: string[],
    onSuccess?: () => void,
  ) => {
    // Reset previous state
    setError(null);
    setSuccess(false);
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
      setSuccess(true);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return { loading, error, success, handleInstallPackages };
}
