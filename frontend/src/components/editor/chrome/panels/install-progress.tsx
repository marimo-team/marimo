/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronDownIcon, ChevronRightIcon, XIcon } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import {
  getInstallationStatusElements,
  ProgressIcon,
  StreamingLogsViewer,
} from "@/components/editor/package-alert";
import { Button } from "@/components/ui/button";
import {
  isInstallingPackageAlert,
  useAlertActions,
  useAlerts,
} from "@/core/alerts/state";
import { cn } from "@/utils/cn";

/**
 * Install progress docked to the bottom of the packages panel.
 *
 * Rendered as an absolutely-positioned card so it floats over the package list
 * rather than pushing it down. Collapsed to a one-line summary by default;
 * expands to show per-package status and streaming logs, and auto-expands on
 * failure so errors aren't hidden.
 */
export const InlineInstallProgress: React.FC = () => {
  const { packageAlert, packageLogs } = useAlerts();
  const { clearPackageAlert } = useAlertActions();
  const [isExpanded, setIsExpanded] = useState(false);

  const isInstalling =
    packageAlert !== null && isInstallingPackageAlert(packageAlert);
  const alertId = packageAlert?.id;
  const statusElements = isInstalling
    ? getInstallationStatusElements(packageAlert.packages)
    : null;
  const status = statusElements?.status;

  // Auto-dismiss shortly after everything installs successfully.
  useEffect(() => {
    if (status === "installed" && alertId) {
      const timeout = setTimeout(() => clearPackageAlert(alertId), 10_000);
      return () => clearTimeout(timeout);
    }
  }, [status, alertId, clearPackageAlert]);

  // Surface errors automatically.
  useEffect(() => {
    if (status === "failed") {
      setIsExpanded(true);
    }
  }, [status]);

  if (!isInstalling || statusElements === null) {
    return null;
  }

  const { title, titleIcon } = statusElements;
  const packages = Object.entries(packageAlert.packages);

  return (
    <div
      className={cn(
        "absolute bottom-0 left-0 right-0 z-10 border-t bg-background",
        "shadow-[0_-2px_8px_rgba(0,0,0,0.08)]",
        status === "failed" && "border-t-destructive",
      )}
    >
      <div className="flex items-center justify-between gap-1 pl-2 pr-1 py-1">
        <button
          type="button"
          className="flex items-center gap-1 text-sm font-medium min-w-0 flex-1 text-left"
          onClick={() => setIsExpanded((expanded) => !expanded)}
        >
          {isExpanded ? (
            <ChevronDownIcon className="w-4 h-4 shrink-0" />
          ) : (
            <ChevronRightIcon className="w-4 h-4 shrink-0" />
          )}
          {titleIcon}
          <span className="truncate">{title}</span>
        </button>
        <Button
          variant="text"
          size="icon"
          data-testid="dismiss-install-progress-button"
          onClick={() => clearPackageAlert(packageAlert.id)}
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>
      {isExpanded && (
        <div className="max-h-64 overflow-auto px-3 pb-3 scrollbar-thin">
          <ul className="list-none">
            {packages.map(([pkg, packageStatus], index) => (
              <li
                key={index}
                className={cn(
                  "flex items-center gap-1 font-mono text-xs",
                  packageStatus === "failed" && "text-destructive",
                )}
              >
                <ProgressIcon status={packageStatus} />
                {pkg}
              </li>
            ))}
          </ul>
          {Object.keys(packageLogs).length > 0 && (
            <StreamingLogsViewer packageLogs={packageLogs} />
          )}
        </div>
      )}
    </div>
  );
};
