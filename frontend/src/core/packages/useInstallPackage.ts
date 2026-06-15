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
      // The backend resolves the whole list as a single transaction, so the
      // response only carries an aggregate success/error. Report a single
      // toast covering all requested packages rather than implying a
      // per-package outcome we don't actually have.
      if (response.success) {
        showAddPackageToast(packages);
      } else {
        showAddPackageToast(packages, response.error);
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
