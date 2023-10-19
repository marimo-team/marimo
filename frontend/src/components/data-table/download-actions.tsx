/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { Button } from "../ui/button";
import { CaretDownIcon } from "@radix-ui/react-icons";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

export interface DownloadActionProps {
  downloadAs: (format: "csv" | "json" | "xls") => Promise<string>;
}

const formats = [
  { label: "CSV", format: "csv" },
  { label: "JSON", format: "json" },
  { label: "Excel", format: "xls" },
] as const;

export const DownloadAs: React.FC<DownloadActionProps> = (props) => {
  const button = (
    <Button size="xs" variant="link">
      Download <CaretDownIcon className="w-3 h-3 ml-1" />
    </Button>
  );

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{button}</DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" className="no-print">
        {formats.map((format) => (
          <DropdownMenuItem
            key={format.label}
            onSelect={async () => {
              const downloadUrl = await props.downloadAs(format.format);
              const link = document.createElement("a");
              link.href = downloadUrl;
              link.setAttribute("download", "download");
              document.body.append(link);
              link.click();
              link.remove();
            }}
          >
            {format.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
