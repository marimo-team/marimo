/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  AlertCircleIcon,
  ClipboardCopyIcon,
  DownloadIcon,
} from "lucide-react";
import React from "react";
import { downloadSizeLimitAtom } from "./download-policy/atoms";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { downloadByURL, withLoadingToast } from "@/utils/download";
import { prettyError } from "@/utils/errors";
import { Filenames } from "@/utils/filenames";
import {
  jsonParseWithSpecialChar,
  jsonToMarkdown,
} from "@/utils/json/json-parser";
import { MissingPackagePrompt } from "../datasources/missing-package-prompt";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";

const EXPORT_OPTIONS = [
  {
    label: "CSV",
    format: "csv",
    description: "Comma-separated values",
    canDownload: true,
    canCopy: true,
  },
  {
    label: "TSV",
    format: "tsv",
    description: "Best for Excel and Google Sheets",
    canDownload: true,
    canCopy: true,
  },
  {
    label: "JSON",
    format: "json",
    description: "Raw JSON data",
    canDownload: true,
    canCopy: true,
  },
  {
    label: "Parquet",
    format: "parquet",
    description: "Columnar binary format",
    canDownload: true,
    canCopy: false,
  },
  {
    label: "Markdown",
    format: "markdown",
    description: "Preserves hyperlinks and formatting",
    canDownload: false,
    canCopy: true,
  },
] as const;

type ExportFormat = (typeof EXPORT_OPTIONS)[number]["format"];
type DownloadFormat = Exclude<ExportFormat, "markdown">;
type CopyFormat = Exclude<ExportFormat, "parquet">;
type ExportAction =
  | { destination: "download"; format: DownloadFormat }
  | { destination: "copy"; format: CopyFormat };

type ExportFailure =
  | {
      kind: "error";
      title: string;
      description: string;
    }
  | {
      kind: "missing-packages";
      title: string;
      description?: string | null;
      packages: string[];
      featureName: string;
      action: ExportAction;
    };

// Each clipboard-copy format fetches from a backend download format, then
// transforms the payload client-side as needed.
const COPY_SOURCE_FORMAT: Record<CopyFormat, DownloadFormat> = {
  csv: "csv",
  tsv: "tsv",
  json: "json",
  markdown: "json",
};

export interface ExportActionProps {
  downloadAs: (req: { format: DownloadFormat }) => Promise<{
    url: string;
    filename: string;
    error?: string | null;
    missing_packages?: string[] | null;
  }>;
  // JSON-serialized size of the currently-rendered data. Used together with
  // downloadSizeLimitAtom to disable the Export button when a host (e.g.,
  // marimo-lsp inside VS Code) declares a download size cap. Null/undefined
  // means "no info" and the gate stays disabled (fail-open).
  sizeBytes?: number | null;
  sizeBytesIsLoading?: boolean;
}

const labelForFormat = (format: ExportFormat): string =>
  EXPORT_OPTIONS.find((option) => option.format === format)?.label ?? format;

const failureTitleForAction = (action: ExportAction): string =>
  action.destination === "download"
    ? "Failed to download"
    : "Failed to copy to clipboard";

const failureDescription = (error: unknown): string =>
  typeof error === "string" ? error : prettyError(error);

export const ExportActions: React.FC<ExportActionProps> = (props) => {
  const [exportDialogOpen, setExportDialogOpen] = React.useState(false);
  const [failure, setFailure] = React.useState<ExportFailure | null>(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const dialogRef = React.useRef<HTMLDivElement>(null);
  const latestActionId = React.useRef(0);
  const policy = useAtomValue(downloadSizeLimitAtom);
  const overLimit = !!(
    policy &&
    props.sizeBytes != null &&
    props.sizeBytes > policy.limitBytes
  );
  const disabled = !!(policy && (props.sizeBytesIsLoading || overLimit));
  const tooltipContent = !disabled
    ? "Export"
    : props.sizeBytesIsLoading
      ? "Checking download size…"
      : policy?.unavailableMessage;

  const button = (
    <Button
      ref={triggerRef}
      data-testid="export-button"
      size="xs"
      variant="text"
      disabled={disabled}
      className={cn(
        "print:hidden text-xs gap-1",
        exportDialogOpen ? "text-primary" : "text-muted-foreground",
      )}
    >
      <DownloadIcon className="w-3.5 h-3.5" />
      Export
    </Button>
  );

  const beginAction = () => {
    const actionId = latestActionId.current + 1;
    latestActionId.current = actionId;
    setFailure(null);
    return actionId;
  };

  const setActionFailure = (actionId: number, nextFailure: ExportFailure) => {
    if (actionId === latestActionId.current) {
      setFailure(nextFailure);
    }
  };

  const resolveDownloadUrl = async (
    format: DownloadFormat,
    action: ExportAction,
    actionId: number,
  ): Promise<{
    url: string;
    filename: string;
  } | null> => {
    const response = await props.downloadAs({ format });

    if (response.missing_packages && response.missing_packages.length > 0) {
      setActionFailure(actionId, {
        kind: "missing-packages",
        title: "Export failed",
        packages: response.missing_packages,
        featureName: `${labelForFormat(action.format)} export`,
        description: response.error,
        action,
      });
      return null;
    }

    if (response.error) {
      setActionFailure(actionId, {
        kind: "error",
        title: failureTitleForAction(action),
        description: response.error,
      });
      return null;
    }

    return {
      url: response.url,
      filename: response.filename,
    };
  };

  const handleDownload = async (format: DownloadFormat) => {
    const action: ExportAction = { destination: "download", format };
    const actionId = beginAction();
    const label = labelForFormat(format);
    try {
      const ok = await withLoadingToast(
        `Preparing ${label} export...`,
        async () => {
          const result = await resolveDownloadUrl(format, action, actionId);
          if (!result) {
            return false;
          }
          const rawName = (result.filename ?? "").trim();
          const baseName = Filenames.withoutExtension(rawName) || "download";
          const downloadName = `${baseName}.${format}`;
          // Append ?download=1 so the server returns Content-Disposition: attachment.
          // This forces a save even when <a download> is ignored — e.g., inside
          // sandboxed iframes that lack `allow-downloads`. Skip for data: URLs
          // (used in pyodide/wasm) since query params would corrupt the payload.
          let downloadUrl = result.url;
          if (!downloadUrl.startsWith("data:")) {
            const separator = downloadUrl.includes("?") ? "&" : "?";
            const params = new URLSearchParams({
              download: "1",
              filename: downloadName,
            });
            downloadUrl = `${downloadUrl}${separator}${params.toString()}`;
          }
          downloadByURL(downloadUrl, downloadName);
          return true;
        },
      );
      if (ok) {
        toast({ title: `${label} download started` });
      }
    } catch (error) {
      setActionFailure(actionId, {
        kind: "error",
        title: failureTitleForAction(action),
        description: failureDescription(error),
      });
    }
  };

  const handleClipboardCopy = async (
    format: CopyFormat,
    action: ExportAction,
    actionId: number,
  ) => {
    await withLoadingToast(
      `Preparing ${labelForFormat(format)} for clipboard...`,
      async () => {
        const sourceFormat = COPY_SOURCE_FORMAT[format];
        const result = await resolveDownloadUrl(sourceFormat, action, actionId);
        if (!result) {
          return;
        }

        let text: string;
        switch (format) {
          case "tsv":
          case "csv":
            text = await fetchText(result.url);
            break;
          case "json": {
            const json = await fetchJson(result.url);
            text = JSON.stringify(json, null, 2);
            break;
          }
          case "markdown": {
            const json = await fetchJson(result.url);
            text = jsonToMarkdown(json);
            break;
          }
          default:
            logNever(format);
            return;
        }

        await copyToClipboard(text);
        toast({
          title: "Copied to clipboard",
        });
      },
    );
  };

  const handleCopyAction = async (format: CopyFormat) => {
    const action: ExportAction = { destination: "copy", format };
    const actionId = beginAction();
    try {
      await handleClipboardCopy(format, action, actionId);
    } catch (error) {
      setActionFailure(actionId, {
        kind: "error",
        title: failureTitleForAction(action),
        description: failureDescription(error),
      });
    }
  };

  const retryAction = (action: ExportAction) => {
    if (action.destination === "download") {
      void handleDownload(action.format);
    } else {
      void handleCopyAction(action.format);
    }
  };

  const handleDialogOpenChange = (open: boolean) => {
    setExportDialogOpen(open);
    if (!open) {
      latestActionId.current += 1;
      setFailure(null);
    }
  };

  return (
    <Dialog open={exportDialogOpen} onOpenChange={handleDialogOpenChange}>
      <Tooltip content={tooltipContent}>
        {disabled ? (
          // Keep the host-limit reason reachable when the nested button is disabled.
          // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          <span tabIndex={0} className="inline-flex">
            {button}
          </span>
        ) : (
          <DialogTrigger asChild={true}>{button}</DialogTrigger>
        )}
      </Tooltip>
      <DialogContent
        ref={dialogRef}
        className="print:hidden gap-4 sm:max-w-[660px]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          dialogRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          triggerRef.current?.focus();
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            handleDialogOpenChange(false);
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Export table</DialogTitle>
          <DialogDescription>Choose one export action.</DialogDescription>
        </DialogHeader>
        <ul
          aria-label="Export formats"
          className="list-none overflow-hidden rounded-lg border bg-card"
        >
          {EXPORT_OPTIONS.map((option) => (
            <li
              key={option.format}
              data-testid={`export-row-${option.format}`}
              className="grid min-h-[62px] grid-cols-[28px_1fr_auto] items-center border-b px-2.5 last:border-b-0 hover:bg-accent/50"
            >
              <span aria-hidden={true} className="h-8 w-7" />
              <div className="grid gap-0.5 pl-1">
                <span className="text-sm font-medium">{option.label}</span>
                <span className="text-xs text-muted-foreground">
                  {option.description}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Tooltip
                  content={
                    option.canDownload
                      ? `Download ${option.label}`
                      : `${option.label} is available for copy only.`
                  }
                >
                  <span className="inline-flex">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Download ${option.label}`}
                      disabled={!option.canDownload}
                      onClick={
                        option.canDownload
                          ? () => {
                              void handleDownload(option.format);
                            }
                          : undefined
                      }
                    >
                      <DownloadIcon className="h-4 w-4" />
                    </Button>
                  </span>
                </Tooltip>
                <Tooltip
                  content={
                    option.canCopy
                      ? `Copy ${option.label}`
                      : `${option.label} is available for download only.`
                  }
                >
                  <span className="inline-flex">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Copy ${option.label}`}
                      disabled={!option.canCopy}
                      onClick={
                        option.canCopy
                          ? () => {
                              void handleCopyAction(option.format);
                            }
                          : undefined
                      }
                    >
                      <ClipboardCopyIcon className="h-4 w-4" />
                    </Button>
                  </span>
                </Tooltip>
              </div>
            </li>
          ))}
        </ul>
        {failure && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <div>
              <AlertTitle>{failure.title}</AlertTitle>
              <AlertDescription>
                {failure.kind === "missing-packages" ? (
                  <MissingPackagePrompt
                    packages={failure.packages}
                    featureName={failure.featureName}
                    description={failure.description}
                    onInstall={() => retryAction(failure.action)}
                    className="items-start"
                  />
                ) : (
                  failure.description
                )}
              </AlertDescription>
            </div>
          </Alert>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            size="xs"
            onClick={() => handleDialogOpenChange(false)}
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

function fetchJson(url: string): Promise<Record<string, unknown>[]> {
  return fetchText(url).then(
    jsonParseWithSpecialChar<Record<string, unknown>[]>,
  );
}

function fetchText(url: string): Promise<string> {
  return fetch(url).then((res) => {
    if (!res.ok) {
      throw new Error(res.statusText);
    }
    return res.text();
  });
}
