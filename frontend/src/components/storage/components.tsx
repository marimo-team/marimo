/* Copyright 2026 Marimo. All rights reserved. */

import {
  CloudIcon,
  FileCodeIcon,
  FileIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileVideoIcon,
  HardDriveIcon,
  ImageIcon,
} from "lucide-react";
import {
  CLOUD_PROTOCOLS,
  type KnownStorageProtocol,
  LOCAL_PROTOCOLS,
} from "@/core/storage/types";

export function renderFileIcon(name: string): React.ReactNode {
  const ext = name.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "png":
    case "jpg":
    case "jpeg":
    case "gif":
    case "svg":
    case "webp":
      return <ImageIcon className="h-3.5 w-3.5 text-purple-500" />;
    case "csv":
    case "parquet":
    case "arrow":
    case "xlsx":
      return <FileSpreadsheetIcon className="h-3.5 w-3.5 text-green-500" />;
    case "py":
    case "js":
    case "ts":
    case "json":
      return <FileCodeIcon className="h-3.5 w-3.5 text-blue-500" />;
    case "mp4":
    case "mpeg":
      return <FileVideoIcon className="h-3.5 w-3.5 text-orange-500" />;
    case "txt":
    case "md":
    case "log":
      return <FileTextIcon className="h-3.5 w-3.5 text-muted-foreground" />;
    default:
      return <FileIcon className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

export function renderProtocolIcon(
  protocol: KnownStorageProtocol | (string & {}),
): React.ReactNode {
  const normalized = protocol.toLowerCase();
  if (CLOUD_PROTOCOLS.has(normalized as KnownStorageProtocol)) {
    return <CloudIcon className="h-3.5 w-3.5" />;
  }
  if (LOCAL_PROTOCOLS.has(normalized as KnownStorageProtocol)) {
    return <HardDriveIcon className="h-3.5 w-3.5" />;
  }
  return <HardDriveIcon className="h-3.5 w-3.5" />;
}
