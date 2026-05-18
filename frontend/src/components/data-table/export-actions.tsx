/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  BracesIcon,
  BrickWallIcon,
  DownloadIcon,
  FileTextIcon,
  TableIcon,
} from "lucide-react";
import React from "react";
import { useLocale } from "react-aria";
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
  jsonToTSV,
} from "@/utils/json/json-parser";
import { MissingPackagePrompt } from "../datasources/missing-package-prompt";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";

const FILE_TYPES = {
  CSV: {
    label: "CSV",
    format: "csv",
    description: "Comma-separated values",
    icon: TableIcon,
  },
  JSON: {
    label: "JSON",
    format: "json",
    description: "Raw JSON data",
    icon: BracesIcon,
  },
  PARQUET: {
    label: "Parquet",
    format: "parquet",
    description: "Columnar binary format",
    icon: BrickWallIcon,
  },
  TSV: {
    label: "TSV",
    format: "tsv",
    description: "Best for Excel and Google Sheets",
    icon: TableIcon,
  },
  MARKDOWN: {
    label: "Markdown",
    format: "markdown",
    description: "Preserves hyperlinks and formatting",
    icon: FileTextIcon,
  },
} as const;

const downloadOptions = [FILE_TYPES.CSV, FILE_TYPES.JSON, FILE_TYPES.PARQUET];
const copyOptions = [
  FILE_TYPES.TSV,
  FILE_TYPES.JSON,
  FILE_TYPES.CSV,
  FILE_TYPES.MARKDOWN,
];

type DownloadFormat = (typeof downloadOptions)[number]["format"];
type CopyFormat = (typeof copyOptions)[number]["format"];

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
}

const labelForDownloadFormat = (format: DownloadFormat): string =>
  downloadOptions.find((opt) => opt.format === format)?.label ?? format;
const labelForCopyFormat = (format: CopyFormat): string =>
  copyOptions.find((opt) => opt.format === format)?.label ?? format;

export const ExportMenu: React.FC<ExportActionProps> = (props) => {
  const { locale } = useLocale();
  const [open, setOpen] = React.useState(false);
  const policy = useAtomValue(downloadSizeLimitAtom);
  const disabled = !!(
    policy &&
    props.sizeBytes != null &&
    props.sizeBytes > policy.limitBytes
  );

  const button = (
    <Button
      data-testid="export-button"
      size="xs"
      variant="text"
      disabled={disabled}
      className={cn(
        "print:hidden text-xs gap-1",
        open ? "text-primary" : "text-muted-foreground",
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
            featureName={`${labelForDownloadFormat(format)} export`}
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
    const label = labelForDownloadFormat(format);
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
      `Preparing ${labelForCopyFormat(format)} for clipboard...`,
      async () => {
        const sourceFormat: DownloadFormat = format === "csv" ? "csv" : "json";
        const result = await resolveDownloadUrl(sourceFormat, () => {
          void handleClipboardCopy(format);
        });
        if (!result) {
          return;
        }

        let text: string;
        switch (format) {
          case "tsv": {
            const json = await fetchJson(result.url);
            text = jsonToTSV(json, locale);
            break;
          }
          case "json": {
            const json = await fetchJson(result.url);
            text = JSON.stringify(json, null, 2);
            break;
          }
          case "csv":
            text = await fetchText(result.url);
            break;
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

  return (
    <DropdownMenu modal={false} open={open} onOpenChange={setOpen}>
      <Tooltip
        content={disabled ? policy?.unavailableMessage : "Export"}
        open={open ? false : undefined}
      >
        <DropdownMenuTrigger asChild={true} disabled={disabled}>
          <span tabIndex={disabled ? 0 : -1} className="inline-flex">
            {button}
          </span>
        </DropdownMenuTrigger>
      </Tooltip>
      <DropdownMenuContent side="bottom" className="print:hidden">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Download
        </DropdownMenuLabel>
        {downloadOptions.map((option) => (
          <DropdownMenuItem
            key={option.label}
            onSelect={() => {
              void handleDownload(option.format);
            }}
          >
            <option.icon className="mo-dropdown-icon" />
            <div className="flex flex-col">
              <span>{option.label}</span>
              <span className="text-xs text-muted-foreground">
                {option.description}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Copy to clipboard
        </DropdownMenuLabel>
        {copyOptions.map((option) => (
          <DropdownMenuItem
            key={option.label}
            onSelect={async () => {
              try {
                await handleClipboardCopy(option.format);
              } catch (error) {
                toast({
                  title: "Failed to copy to clipboard",
                  description: prettyError(error),
                  variant: "danger",
                });
              }
            }}
          >
            <option.icon className="mo-dropdown-icon" />
            <div className="flex flex-col">
              <span>{option.label}</span>
              <span className="text-xs text-muted-foreground">
                {option.description}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
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
