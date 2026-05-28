/* Copyright 2026 Marimo. All rights reserved. */

import { Kbd } from "@/components/ui/kbd";
import { toast } from "@/components/ui/use-toast";

/**
 * Renders package-manager error output. The output is often multi-line (e.g.
 * pip/uv dependency resolution errors), so show it in a scrollable monospace
 * block rather than collapsing it into a single line.
 */
const PackageErrorDescription = ({ error }: { error: string }) => (
  <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-xs scrollbar-thin">
    {error}
  </pre>
);

export const showAddPackageToast = (
  packageName: string,
  error?: string | null,
) => {
  if (error) {
    toast({
      title: "Failed to add package",
      description: <PackageErrorDescription error={error} />,
      variant: "danger",
    });
  } else {
    toast({
      title: "Package added",
      description: (
        <div>
          <div>
            The package <Kbd className="inline">{packageName}</Kbd> and its
            dependencies has been added to your environment.
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
      description: <PackageErrorDescription error={error} />,
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
