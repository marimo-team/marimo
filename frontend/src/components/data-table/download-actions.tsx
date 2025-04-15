/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Button } from "../ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { toast } from "../ui/use-toast";
import { downloadByURL } from "@/utils/download";
import {
  BracesIcon,
  BrickWallIcon,
  ChevronDownIcon,
  TableIcon,
} from "lucide-react";

export interface DownloadActionProps {
  downloadAs: (req: { format: "csv" | "json" | "parquet" }) => Promise<string>;
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

export const DownloadAs: React.FC<DownloadActionProps> = (props) => {
  const button = (
    <Button data-testid="download-as-button" size="xs" variant="link">
      Download <ChevronDownIcon className="w-3 h-3 ml-1" />
    </Button>
  );

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" className="no-print">
        {options.map((option) => (
          <DropdownMenuItem
            key={option.label}
            onSelect={async () => {
              const downloadUrl = await props
                .downloadAs({
                  format: option.format,
                })
                .catch((error) => {
                  toast({
                    title: "Failed to download",
                    description:
                      "message" in error ? error.message : String(error),
                  });
                });
              if (!downloadUrl) {
                return;
              }
              const ext = option.format;
              downloadByURL(downloadUrl, `download.${ext}`);
            }}
          >
            <option.icon className="mo-dropdown-icon" />
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
