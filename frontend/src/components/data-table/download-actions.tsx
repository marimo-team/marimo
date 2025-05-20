/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { toast } from "../ui/use-toast";
import { downloadByURL } from "@/utils/download";
import {
  BracesIcon,
  BrickWallIcon,
  ChevronDownIcon,
  ClipboardListIcon,
  TableIcon,
} from "lucide-react";
import { jsonToTSV } from "@/utils/json/json-parser";
import { copyToClipboard } from "@/utils/copy";
import { logNever } from "@/utils/assertNever";

type DownloadFormat = "csv" | "json" | "parquet";

export interface DownloadActionProps {
  downloadAs: (req: { format: DownloadFormat }) => Promise<string>;
}

const options = [
  {
    label: "CSV",
    format: "csv",
    icon: TableIcon,
  },
  {
    label: "JSON",
    format: "json",
    icon: BracesIcon,
  },
  {
    label: "Parquet",
    format: "parquet",
    icon: BrickWallIcon,
  },
] as const;

const clipboardOptions = [
  {
    label: "TSV",
    format: "tsv",
    description: "Best for Excel and Google Sheets",
    icon: TableIcon,
  },
  {
    label: "JSON",
    format: "json",
    description: "Raw JSON data",
    icon: BracesIcon,
  },
  {
    label: "CSV",
    format: "csv",
    description: "Comma-separated values",
    icon: TableIcon,
  },
] as const;

export const DownloadAs: React.FC<DownloadActionProps> = (props) => {
  const button = (
    <Button data-testid="download-as-button" size="xs" variant="link">
      Download <ChevronDownIcon className="w-3 h-3 ml-1" />
    </Button>
  );

  const getDownloadUrl = (format: DownloadFormat) => {
    return props.downloadAs({ format }).catch((error) => {
      toast({
        title: "Failed to download",
        description: "message" in error ? error.message : String(error),
      });
      throw error;
    });
  };

  const handleClipboardCopy = async (
    format: (typeof clipboardOptions)[number]["format"],
  ) => {
    let text: string;

    switch (format) {
      case "tsv": {
        const downloadUrl = await getDownloadUrl("json");
        const json = await fetchJson(downloadUrl);
        text = jsonToTSV(json);
        break;
      }
      case "json": {
        const downloadUrl = await getDownloadUrl("json");
        const json = await fetchJson(downloadUrl);
        text = JSON.stringify(json, null, 2);
        break;
      }
      case "csv": {
        const downloadUrl = await getDownloadUrl("csv");
        const csv = await fetchText(downloadUrl);
        text = csv;
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
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" className="no-print">
        {options.map((option) => (
          <DropdownMenuItem
            key={option.label}
            onSelect={async () => {
              const downloadUrl = await getDownloadUrl(option.format);
              const ext = option.format;
              downloadByURL(downloadUrl, `download.${ext}`);
            }}
          >
            <option.icon className="mo-dropdown-icon" />
            {option.label}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <ClipboardListIcon className="mo-dropdown-icon" />
            Copy to clipboard
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {clipboardOptions.map((option) => (
              <DropdownMenuItem
                key={option.label}
                onSelect={() => handleClipboardCopy(option.format)}
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
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

function fetchJson(url: string): Promise<Array<Record<string, unknown>>> {
  return fetch(url).then((res) => {
    if (!res.ok) {
      throw new Error(res.statusText);
    }
    return res.json();
  });
}

function fetchText(url: string): Promise<string> {
  return fetch(url).then((res) => {
    if (!res.ok) {
      throw new Error(res.statusText);
    }
    return res.text();
  });
}
