/* Copyright 2026 Marimo. All rights reserved. */

import { ArrowLeftIcon, DownloadIcon, RefreshCwIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";

interface FilePreviewHeaderProps {
  filename?: string;
  filenameIcon?: React.ReactNode;
  onBack?: () => void;
  onRefresh?: () => void;
  onDownload?: () => void;
  /** Extra action buttons placed before the download button. */
  actions?: React.ReactNode;
}

export const FilePreviewHeader: React.FC<FilePreviewHeaderProps> = ({
  filename,
  filenameIcon,
  onBack,
  onRefresh,
  onDownload,
  actions,
}) => {
  return (
    <div className="flex items-center shrink-0 border-b px-1 gap-1">
      {onBack && (
        <Tooltip content="Back to file list">
          <Button variant="text" size="xs" onClick={onBack}>
            <ArrowLeftIcon className="h-4 w-4" />
          </Button>
        </Tooltip>
      )}
      {filename ? (
        <span className="flex items-center gap-1.5 flex-1 min-w-0 text-xs font-semibold truncate">
          {filenameIcon}
          {filename}
        </span>
      ) : (
        <span className="flex-1" />
      )}
      <div className="flex items-center gap-0.5 shrink-0">
        {onRefresh && (
          <Tooltip content="Refresh">
            <Button variant="text" size="xs" onClick={onRefresh}>
              <RefreshCwIcon className="h-3.5 w-3.5" />
            </Button>
          </Tooltip>
        )}
        {actions}
        {onDownload && (
          <Tooltip content="Download">
            <Button variant="text" size="xs" onClick={onDownload}>
              <DownloadIcon className="h-3.5 w-3.5" />
            </Button>
          </Tooltip>
        )}
      </div>
    </div>
  );
};
