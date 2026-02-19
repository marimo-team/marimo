/* Copyright 2026 Marimo. All rights reserved. */

import AwsIcon from "@marimo-team/llm-info/icons/aws.svg?inline";
import AzureIcon from "@marimo-team/llm-info/icons/azure.svg?inline";
import {
  DatabaseZapIcon,
  FileCodeIcon,
  FileIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileVideoIcon,
  GlobeIcon,
  HardDriveIcon,
  ImageIcon,
} from "lucide-react";
import GoogleCloudIcon from "@/components/databases/icons/google-cloud-storage.svg?inline";
import type { KnownStorageProtocol } from "@/core/storage/types";

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

const PROTOCOL_ICONS: Record<
  KnownStorageProtocol,
  string | React.ComponentType<{ className?: string }>
> = {
  s3: AwsIcon,
  azure: AzureIcon,
  gcs: GoogleCloudIcon,
  http: GlobeIcon,
  file: HardDriveIcon,
  "in-memory": DatabaseZapIcon,
} as const;

export function renderProtocolIcon(
  protocol: KnownStorageProtocol | (string & {}),
): React.ReactNode {
  const Icon =
    PROTOCOL_ICONS[protocol.toLowerCase() as KnownStorageProtocol] ??
    HardDriveIcon;
  if (typeof Icon === "string") {
    return <img src={Icon} alt={protocol} className="h-3.5 w-3.5" />;
  }
  return <Icon className="h-3.5 w-3.5" />;
}
