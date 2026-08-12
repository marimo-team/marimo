/* Copyright 2026 Marimo. All rights reserved. */

import { DownloadIcon } from "lucide-react";
import { useLocale } from "react-aria";
import { Button } from "@/components/ui/button";
import type { FileInfo } from "@/core/network/types";
import { formatBytes } from "@/utils/formatting";

interface Props {
  file: FileInfo;
  mimeType: string;
  message: string;
  onDownload?: () => void;
}

export const FilePreviewMetadata = ({
  file,
  mimeType,
  message,
  onDownload,
}: Props) => {
  const { locale } = useLocale();
  return (
    <div className="p-4 text-sm">
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
        <span className="text-muted-foreground font-medium">Path</span>
        <span className="font-mono text-xs break-all">{file.path}</span>
        <span className="text-muted-foreground font-medium">Type</span>
        <span>{mimeType}</span>
        {file.size != null && (
          <>
            <span className="text-muted-foreground font-medium">Size</span>
            <span>{formatBytes(file.size, locale)}</span>
          </>
        )}
      </div>
      <div className="mt-4 text-muted-foreground italic">{message}</div>
      {onDownload && (
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={onDownload}
        >
          <DownloadIcon className="h-3.5 w-3.5 mr-2" />
          Download
        </Button>
      )}
    </div>
  );
};
