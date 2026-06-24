/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import { Button } from "@/components/ui/button";
import { useInstallAllowed } from "@/core/mode";
import { useInstallPackages } from "@/core/packages/useInstallPackage";
import { cn } from "@/utils/cn";

interface InstallPackageButtonProps {
  packages: string[] | undefined;
  showMaxPackages?: number;
  className?: string;
  onInstall?: () => void;
}

/**
 * Button to install missing packages
 * Opens the packages panel and focuses the input
 */
export const InstallPackageButton: React.FC<InstallPackageButtonProps> = ({
  packages,
  showMaxPackages,
  className,
  onInstall,
}) => {
  const { handleInstallPackages } = useInstallPackages();
  const installAllowed = useInstallAllowed();

  if (!packages || packages.length === 0 || !installAllowed) {
    return null;
  }

  return (
    <Button
      variant="outline"
      size="xs"
      onClick={() => {
        handleInstallPackages(packages, onInstall);
      }}
      className={cn("ml-2", className)}
    >
      Install{" "}
      {showMaxPackages
        ? packages.slice(0, showMaxPackages).join(", ")
        : packages.join(", ")}
    </Button>
  );
};
