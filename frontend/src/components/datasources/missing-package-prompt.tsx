/* Copyright 2026 Marimo. All rights reserved. */

import { useInstallAllowed } from "@/core/mode";
import { cn } from "@/utils/cn";
import { InstallPackageButton } from "./install-package-button";

interface MissingPackagePromptProps {
  packages: string[];
  featureName: string;
  description?: string | null; // server message, suppressing this in read-only mode
  onInstall?: () => void;
  className?: string;
}

/**
 * display missing-package requirement with mode-aware copy. In edit mode,
 * shows the backend explanation (if any) plus an install button for missing-packages.
 * read mode, shows a generic "isn't available"
 */
export const MissingPackagePrompt: React.FC<MissingPackagePromptProps> = ({
  packages,
  featureName,
  description,
  onInstall,
  className,
}) => {
  const installAllowed = useInstallAllowed();

  if (!installAllowed) {
    return (
      <span className={cn("text-xs", className)}>
        {featureName} isn't available in this notebook
      </span>
    );
  }

  return (
    <div className={cn("text-xs flex flex-col items-end gap-2", className)}>
      <span className="self-start">
        {description || `${featureName} requires ${packages.join(", ")}`}
      </span>
      <InstallPackageButton
        packages={packages}
        onInstall={onInstall}
        className="ml-0"
      />
    </div>
  );
};
