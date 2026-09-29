/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { CopyIcon, DownloadIcon } from "lucide-react";
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

export const ExportActions: React.FC<ExportActionProps> = (props) => {
  const [exportDialogOpen, setExportDialogOpen] = React.useState(false);
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

  const resolveDownloadUrl = async (
    format: DownloadFormat,
    onRetry: () => void,
  ): Promise<{
    url: string;
    filename: string;
  } | null> => {
    let response: Awaited<ReturnType<typeof props.downloadAs>>;
    try {
      response = await props.downloadAs({ format });
    } catch (error) {
      toast({
        title: "Failed to download",
        description:
          error != null && typeof error === "object" && "message" in error
            ? String(error.message)
            : String(error),
      });
      return null;
    }

    if (response.missing_packages && response.missing_packages.length > 0) {
      toast({
        title: "Export failed",
        description: (
          <MissingPackagePrompt
            packages={response.missing_packages}
            featureName={`${labelForFormat(format)} export`}
            description={response.error}
            onInstall={onRetry}
          />
        ),
      });
      return null;
    }

    return {
      url: response.url,
      filename: response.filename,
    };
  };

  const handleDownload = async (format: DownloadFormat) => {
    const label = labelForFormat(format);
    const ok = await withLoadingToast(
      `Preparing ${label} export...`,
      async () => {
        const result = await resolveDownloadUrl(format, () => {
          void handleDownload(format);
        });
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
  };

  const handleClipboardCopy = async (format: CopyFormat) => {
    await withLoadingToast(
      `Preparing ${labelForFormat(format)} for clipboard...`,
      async () => {
        const sourceFormat = COPY_SOURCE_FORMAT[format];
        const result = await resolveDownloadUrl(sourceFormat, () => {
          void handleClipboardCopy(format);
        });
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
    try {
      await handleClipboardCopy(format);
    } catch (error) {
      toast({
        title: "Failed to copy to clipboard",
        description: prettyError(error),
        variant: "danger",
      });
    }
  };

  return (
    <Dialog open={exportDialogOpen} onOpenChange={setExportDialogOpen}>
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
        className="print:hidden gap-4 sm:max-w-[660px]"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setExportDialogOpen(false);
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
                      <CopyIcon className="h-4 w-4" />
                    </Button>
                  </span>
                </Tooltip>
              </div>
            </li>
          ))}
        </ul>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            size="xs"
            onClick={() => setExportDialogOpen(false)}
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
