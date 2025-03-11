/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Button } from "@/components/ui/button";
import { store } from "@/core/state/jotai";
import { chromeAtom } from "@/components/editor/chrome/state";
import { packagesToInstallAtom } from "@/components/editor/chrome/panels/packages-state";

interface InstallPackageButtonProps {
  packages: string[] | undefined;
}

/**
 * Button to install missing packages
 * Opens the packages panel and focuses the input
 */
export const InstallPackageButton: React.FC<InstallPackageButtonProps> = ({
  packages,
}) => {
  if (!packages || packages.length === 0) {
    return null;
  }

  const handleClick = () => {
    const packagesString = packages.join(", ");

    // Set the packages to install
    store.set(packagesToInstallAtom, packagesString);

    // Open the packages panel
    store.set(chromeAtom, (prev) => ({
      ...prev,
      isSidebarOpen: true,
      selectedPanel: "packages",
    }));
  };

  return (
    <Button variant="outline" size="xs" onClick={handleClick} className="ml-2">
      Install {packages.join(", ")}
    </Button>
  );
};
