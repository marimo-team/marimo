/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Button } from "@/components/ui/button";
import { useChromeActions } from "@/components/editor/chrome/state";
import { packagesToInstallAtom } from "@/components/editor/chrome/panels/packages-state";
import { useSetAtom } from "jotai";
import { cn } from "@/utils/cn";

interface InstallPackageButtonProps {
  packages: string[] | undefined;
  className?: string;
}

/**
 * Button to install missing packages
 * Opens the packages panel and focuses the input
 */
export const InstallPackageButton: React.FC<InstallPackageButtonProps> = ({
  packages,
  className,
}) => {
  const chromeActions = useChromeActions();
  const setPackagesToInstall = useSetAtom(packagesToInstallAtom);

  if (!packages || packages.length === 0) {
    return null;
  }

  const handleClick = () => {
    const packagesString = packages.join(", ");

    // Set the packages to install
    setPackagesToInstall(packagesString);

    // Open the packages panel
    chromeActions.openApplication("packages");
  };

  return (
    <Button
      variant="outline"
      size="xs"
      onClick={handleClick}
      className={cn("ml-2", className)}
    >
      Install {packages.join(", ")}
    </Button>
  );
};
