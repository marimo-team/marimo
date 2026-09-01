/* Copyright 2026 Marimo. All rights reserved. */

import { AlertCircleIcon, DownloadCloudIcon } from "lucide-react";
import type { PropsWithChildren } from "react";
import { Spinner } from "@/components/icons/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { assertNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import type {
  ExportBlockReason,
  ExportFormat,
  ExportFormatStatus,
  ExportSetupRequirement,
} from "./state";

const SETUP_REQUIREMENTS: Record<
  ExportSetupRequirement["name"],
  { description: string }
> = {
  "playwright-chromium": {
    description: "PDF export requires Playwright Chromium.",
  },
};

export function FormatStatusIcon({ status }: { status: ExportFormatStatus }) {
  if (status.available && !status.availabilityCheckFailed) {
    return null;
  }
  if (status.reason?.type === "checking-requirements") {
    return (
      <span className="ml-auto flex shrink-0">
        <Spinner size="small" className="size-3" />
        <span className="sr-only">Checking requirements</span>
      </span>
    );
  }
  const statusLabel = status.availabilityCheckFailed
    ? "Requirements unknown"
    : "Unavailable";
  return (
    <span className="ml-auto flex shrink-0">
      <AlertCircleIcon
        className={cn(
          "size-3",
          status.availabilityCheckFailed
            ? "text-muted-foreground"
            : "text-(--yellow-11)",
        )}
      />
      <span className="sr-only">{statusLabel}</span>
    </span>
  );
}

export function FormatNotice({
  format,
  formatLabel,
  status,
  onInstall,
  isInstalling = false,
}: {
  format: ExportFormat;
  formatLabel: string;
  status: ExportFormatStatus;
  onInstall?: () => void;
  isInstalling?: boolean;
}) {
  if (status.availabilityCheckFailed) {
    return (
      <div className="mb-2.5">
        <Notice>
          Couldn't check whether this export is available. You can still try it.
        </Notice>
      </div>
    );
  }
  if (!status.reason) {
    return null;
  }

  return (
    <div className="mb-2.5">
      <ReasonNotice
        format={format}
        formatLabel={formatLabel}
        reason={status.reason}
        onInstall={onInstall}
        isInstalling={isInstalling}
      />
    </div>
  );
}

function Notice({
  children,
  onInstall,
  isInstalling = false,
}: PropsWithChildren<{
  onInstall?: () => void;
  isInstalling?: boolean;
}>) {
  return (
    <Alert
      variant="warning"
      className="flex items-center gap-2.5 px-3 py-2 text-(--yellow-12) has-[svg]:pl-3 [&>svg]:static [&>svg+div]:translate-y-0"
    >
      <AlertCircleIcon className="size-4 shrink-0" />
      <AlertDescription className="flex min-w-0 flex-1 items-center gap-3 text-sm leading-5">
        <span className="min-w-0 flex-1">{children}</span>
        {onInstall ? (
          <Button
            type="button"
            variant="outline"
            size="xs"
            className="shrink-0 border-input bg-background text-foreground hover:border-input hover:bg-muted hover:text-foreground"
            disabled={isInstalling}
            aria-busy={isInstalling}
            onClick={onInstall}
          >
            {isInstalling ? (
              <Spinner size="small" className="mr-1.5 size-3.5" />
            ) : (
              <DownloadCloudIcon className="mr-1.5 size-3.5" />
            )}
            Install
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  );
}

function ReasonNotice({
  format,
  formatLabel,
  reason,
  onInstall,
  isInstalling,
}: {
  format: ExportFormat;
  formatLabel: string;
  reason: ExportBlockReason;
  onInstall?: () => void;
  isInstalling: boolean;
}) {
  switch (reason.type) {
    case "checking-requirements":
      return (
        <Alert
          role="status"
          variant="info"
          className="flex items-center gap-2.5 p-3 has-[svg]:pl-3 [&>svg]:static [&>svg+div]:translate-y-0"
        >
          <Spinner className="size-4 shrink-0" size="small" />
          <AlertDescription className="min-w-0 flex-1 text-sm leading-5">
            Checking {formatLabel} requirements…
          </AlertDescription>
        </Alert>
      );
    case "notebook-must-be-named":
      return <Notice>Name and save this notebook before exporting.</Notice>;
    case "missing-packages":
      return (
        <Notice onInstall={onInstall} isInstalling={isInstalling}>
          {formatLabel} export requires{" "}
          <code className="break-words font-mono">
            {reason.packages.join(", ")}
          </code>
          .
        </Notice>
      );
    case "missing-setup":
      return (
        <Notice onInstall={onInstall} isInstalling={isInstalling}>
          {onInstall ? (
            reason.requirements
              .map(
                (requirement) =>
                  SETUP_REQUIREMENTS[requirement.name].description,
              )
              .join(" ")
          ) : (
            <span className="block min-w-0">
              {reason.requirements.map((requirement) => {
                const details = SETUP_REQUIREMENTS[requirement.name];
                return (
                  <span className="block" key={requirement.name}>
                    {details.description}
                    <code className="mt-1 block break-all font-mono">
                      {requirement.command}
                    </code>
                  </span>
                );
              })}
            </span>
          )}
        </Notice>
      );
    case "wasm-runtime":
      return (
        <Notice>
          {format === "pdf"
            ? "Use your browser's print dialog to save the current app view as a PDF."
            : "Open this notebook in a local marimo session to use this export."}
        </Notice>
      );
    default:
      assertNever(reason);
  }
}
