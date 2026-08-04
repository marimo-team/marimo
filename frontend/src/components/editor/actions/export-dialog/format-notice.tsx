/* Copyright 2026 Marimo. All rights reserved. */

import { AlertCircleIcon } from "lucide-react";
import type { PropsWithChildren } from "react";
import { Spinner } from "@/components/icons/spinner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { assertNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import type {
  ExportBlockReason,
  ExportFormat,
  ExportFormatStatus,
  ExportSetupRequirement,
} from "./state";

const SETUP_REQUIREMENTS: Record<
  ExportSetupRequirement,
  { description: string; command: string }
> = {
  "playwright-chromium": {
    description: "PDF export requires Playwright Chromium.",
    command: "python -m playwright install chromium",
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
}: {
  format: ExportFormat;
  formatLabel: string;
  status: ExportFormatStatus;
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
      />
    </div>
  );
}

function Notice({ children }: PropsWithChildren) {
  return (
    <Alert
      variant="warning"
      className="flex items-start gap-2.5 p-3 text-(--yellow-12) has-[svg]:pl-3 sm:items-center [&>svg]:static [&>svg+div]:translate-y-0"
    >
      <AlertCircleIcon className="mt-0.5 size-4 shrink-0 sm:mt-0" />
      <AlertDescription className="min-w-0 flex-1 text-sm leading-5">
        {children}
      </AlertDescription>
    </Alert>
  );
}

function ReasonNotice({
  format,
  formatLabel,
  reason,
}: {
  format: ExportFormat;
  formatLabel: string;
  reason: ExportBlockReason;
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
        <Notice>
          Install{" "}
          <code className="break-words font-mono">
            {reason.packages.join(", ")}
          </code>{" "}
          where marimo is running to use this export.
        </Notice>
      );
    case "missing-setup":
      return (
        <Notice>
          <span className="block min-w-0">
            {reason.requirements.map((requirement) => {
              const details = SETUP_REQUIREMENTS[requirement];
              return (
                <span className="block" key={requirement}>
                  {details.description}
                  <code className="mt-1 block break-all font-mono">
                    {details.command}
                  </code>
                </span>
              );
            })}
          </span>
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
