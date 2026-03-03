/* Copyright 2026 Marimo. All rights reserved. */

import { FileIcon, LoaderCircle, RefreshCwIcon } from "lucide-react";
import type React from "react";
import { useCallback } from "react";
import { useLocale } from "react-aria";
import { FilePreviewHeader } from "@/components/editor/file-tree/file-header";
import {
  FileContentRenderer,
  isMediaMime,
} from "@/components/editor/file-tree/renderers";
import { toast } from "@/components/ui/use-toast";
import { DownloadStorage } from "@/core/storage/request-registry";
import type { StorageEntry } from "@/core/storage/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { downloadByURL } from "@/utils/download";
import { formatBytes } from "@/utils/formatting";
import { Logger } from "@/utils/Logger";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { Button } from "../ui/button";
import { renderFileIcon } from "./components";

const MAX_MEDIA_PREVIEW_SIZE = 100 * 1024 * 1024; // 100 MB

interface Props {
  entry: StorageEntry;
  namespace: string;
  onBack: () => void;
}

function displayName(path: string): string {
  const trimmed = path.endsWith("/") ? path.slice(0, -1) : path;
  const parts = trimmed.split("/");
  return parts[parts.length - 1] || trimmed;
}

type PreviewData =
  | { type: "media"; url: string }
  | { type: "text"; content: string };

export const StorageFileViewer: React.FC<Props> = ({
  entry,
  namespace,
  onBack,
}) => {
  const { locale } = useLocale();
  const name = displayName(entry.path);
  const mime = entry.mimeType || "text/plain";
  const isMedia = isMediaMime(mime);
  const tooLargeForMedia =
    isMedia && entry.size > MAX_MEDIA_PREVIEW_SIZE && entry.size > 0;

  const {
    data: preview,
    isPending,
    error,
    refetch,
  } = useAsyncData(async (): Promise<PreviewData | null> => {
    if (tooLargeForMedia) {
      return null;
    }

    const result = await DownloadStorage.request({
      namespace,
      path: entry.path,
      preview: !isMedia,
    });
    if (result.error) {
      throw new Error(result.error);
    }
    if (!result.url) {
      throw new Error("No URL returned");
    }

    if (isMedia) {
      return { type: "media", url: result.url };
    }

    const resp = await fetch(result.url);
    if (!resp.ok) {
      throw new Error(`Failed to fetch preview: ${resp.statusText}`);
    }
    const content = await resp.text();
    return { type: "text", content };
  }, [namespace, entry.path, isMedia, tooLargeForMedia]);

  const handleDownload = useCallback(async () => {
    try {
      const result = await DownloadStorage.request({
        namespace,
        path: entry.path,
      });
      if (result.error) {
        toast({
          title: "Download failed",
          description: result.error,
          variant: "danger",
        });
        return;
      }
      if (result.url) {
        downloadByURL(result.url, result.filename ?? name);
      }
    } catch (error_) {
      Logger.error("Failed to download storage entry", error_);
      toast({
        title: "Download failed",
        description: String(error_),
        variant: "danger",
      });
    }
  }, [namespace, entry.path, name]);

  const header = (
    <FilePreviewHeader
      filename={name}
      filenameIcon={renderFileIcon(name)}
      onBack={onBack}
      onDownload={handleDownload}
    />
  );

  const renderMetadata = ({
    includeMime = false,
  }: {
    includeMime?: boolean;
  }) => {
    return (
      <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 p-4 text-xs">
        <span className="text-muted-foreground font-medium">Path</span>
        <div className="truncate flex items-center gap-1.5">
          <span className="font-mono text-[11px]">{entry.path}</span>
          <CopyClipboardIcon value={entry.path} className="h-3 w-3" />
        </div>

        {includeMime && (
          <span className="text-muted-foreground font-medium">Type</span>
        )}
        {includeMime && <span>{mime}</span>}
        {entry.size > 0 && (
          <>
            <span className="text-muted-foreground font-medium">Size</span>
            <span>{formatBytes(entry.size, locale)}</span>
          </>
        )}
        {entry.lastModified != null && (
          <>
            <span className="text-muted-foreground font-medium">Modified</span>
            <span>{new Date(entry.lastModified * 1000).toLocaleString()}</span>
          </>
        )}
      </div>
    );
  };

  if (tooLargeForMedia) {
    return (
      <div className="flex flex-col h-full">
        {header}
        {renderMetadata({ includeMime: true })}
        <div className="px-4 pb-4 text-xs text-muted-foreground italic">
          File is too large to preview ({formatBytes(entry.size, locale)}).
        </div>
      </div>
    );
  }

  if (isPending) {
    return (
      <div className="flex flex-col h-full">
        {header}
        {renderMetadata({})}
        <div className="flex-1 flex items-center justify-center gap-2 text-xs text-muted-foreground min-h-24">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Loading preview...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        {header}
        {renderMetadata({ includeMime: true })}
        <div className="px-4 pb-4 text-xs text-destructive">
          Failed to load preview: {error.message}
        </div>
        <div className="px-4 pb-4">
          <Button variant="secondary" size="xs" onClick={refetch}>
            <RefreshCwIcon className="h-3 w-3 mr-1" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (preview) {
    return (
      <div className="flex flex-col h-full">
        {header}
        {renderMetadata({})}
        <FileContentRenderer
          mimeType={mime}
          contents={preview.type === "text" ? preview.content : undefined}
          mediaSource={
            preview.type === "media" ? { url: preview.url } : undefined
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {header}
      {renderMetadata({ includeMime: true })}
      <div className="p-4 flex items-center gap-2 text-xs text-muted-foreground">
        <FileIcon className="h-4 w-4" />
        Preview not available for this file type.
      </div>
    </div>
  );
};
