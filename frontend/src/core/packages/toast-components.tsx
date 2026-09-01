/* Copyright 2026 Marimo. All rights reserved. */

import { Kbd } from "@/components/ui/kbd";
import { toast } from "@/components/ui/use-toast";

export const showAddPackageToast = (
  packageName: string | string[],
  error?: string | null,
) => {
  const packageNames = Array.isArray(packageName) ? packageName : [packageName];
  if (error) {
    toast({
      title:
        packageNames.length > 1
          ? "Failed to add packages"
          : "Failed to add package",
      description: error,
      variant: "danger",
    });
  } else {
    toast({
      title: packageNames.length > 1 ? "Packages added" : "Package added",
      description: (
        <div>
          <div>
            {packageNames.length > 1 ? "The packages " : "The package "}
            {packageNames.map((name, index) => (
              <span key={name}>
                {index > 0 && ", "}
                <Kbd className="inline">{name}</Kbd>
              </span>
            ))}{" "}
            and {packageNames.length > 1 ? "their" : "its"} dependencies have
            been added to your environment.
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Some Python packages may require a kernel restart to see changes.
          </div>
        </div>
      ),
    });
  }
};

export const showUpgradePackageToast = (
  packageName: string,
  error?: string | null,
) => {
  if (error) {
    toast({
      title: "Failed to upgrade package",
      description: error,
      variant: "danger",
    });
  } else {
    toast({
      title: "Package upgraded",
      description: (
        <div>
          <div>
            The package <Kbd className="inline">{packageName}</Kbd> has been
            upgraded.
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Some Python packages may require a kernel restart to see changes.
          </div>
        </div>
      ),
    });
  }
};

export const showRemovePackageToast = (
  packageName: string,
  error?: string | null,
) => {
  if (error) {
    toast({
      title: "Failed to remove package",
      description: error,
      variant: "danger",
    });
  } else {
    toast({
      title: "Package removed",
      description: (
        <div>
          <div>
            The package <Kbd className="inline">{packageName}</Kbd> has been
            removed from your environment.
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Some Python packages may require a kernel restart to see changes.
          </div>
        </div>
      ),
    });
  }
};
