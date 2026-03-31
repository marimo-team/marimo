/* Copyright 2026 Marimo. All rights reserved. */

import {
  BracesIcon,
  BrickWallIcon,
  DownloadIcon,
  FileTextIcon,
  TableIcon,
} from "lucide-react";
import React from "react";
import { useLocale } from "react-aria";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { downloadByURL } from "@/utils/download";
import { prettyError } from "@/utils/errors";
import { Filenames } from "@/utils/filenames";
import {
  jsonParseWithSpecialChar,
  jsonToMarkdown,
  jsonToTSV,
} from "@/utils/json/json-parser";
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

type DownloadFormat = "csv" | "json" | "parquet";

export interface ExportActionProps {
  downloadAs: (req: { format: DownloadFormat }) => Promise<{
    url: string;
    filename: string;
  }>;
}

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

export const ExportMenu: React.FC<ExportActionProps> = (props) => {
  const { locale } = useLocale();
  const [open, setOpen] = React.useState(false);

  const button = (
    <Button
      data-testid="export-button"
      size="xs"
      variant="text"
      className={cn(
        "print:hidden text-xs gap-1",
        open ? "text-primary" : "text-muted-foreground",
      )}
    >
      <DownloadIcon className="w-3.5 h-3.5" />
      Export
    </Button>
  );

  const getDownloadResult = (format: DownloadFormat) => {
    return props.downloadAs({ format }).catch((error) => {
      toast({
        title: "Failed to download",
        description: "message" in error ? error.message : String(error),
      });
      throw error;
    });
  };

  const handleClipboardCopy = async (
    format: (typeof copyOptions)[number]["format"],
  ) => {
    let text: string;

    switch (format) {
      case "tsv": {
        const { url } = await getDownloadResult("json");
        const json = await fetchJson(url);
        text = jsonToTSV(json, locale);
        break;
      }
      case "json": {
        const { url } = await getDownloadResult("json");
        const json = await fetchJson(url);
        text = JSON.stringify(json, null, 2);
        break;
      }
      case "csv": {
        const { url } = await getDownloadResult("csv");
        const csv = await fetchText(url);
        text = csv;
        break;
      }
      case "markdown": {
        const { url } = await getDownloadResult("json");
        const json = await fetchJson(url);
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
  };

  return (
    <DropdownMenu modal={false} open={open} onOpenChange={setOpen}>
      <Tooltip content="Export" open={open ? false : undefined}>
        <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      </Tooltip>
      <DropdownMenuContent side="bottom" className="print:hidden">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Download
        </DropdownMenuLabel>
        {downloadOptions.map((option) => (
          <DropdownMenuItem
            key={option.label}
            onSelect={async () => {
              const { url, filename } = await getDownloadResult(option.format);
              const ext = option.format;
              const rawName = (filename ?? "").trim();
              const baseName =
                Filenames.withoutExtension(rawName) || "download";
              downloadByURL(url, `${baseName}.${ext}`);
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
