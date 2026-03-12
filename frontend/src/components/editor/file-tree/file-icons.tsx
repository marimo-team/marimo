/* Copyright 2026 Marimo. All rights reserved. */

import {
  FileAudioIcon,
  FileCodeIcon,
  FileIcon,
  FileJsonIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  FileVideoIcon,
  FolderArchiveIcon,
  FolderIcon,
  ImageIcon,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/utils/cn";

export type FileIconType =
  | "directory"
  | "python"
  | "code"
  | "json"
  | "text"
  | "image"
  | "audio"
  | "video"
  | "data"
  | "pdf"
  | "zip"
  | "unknown";

const EXT_TO_TYPE: Record<string, FileIconType> = {
  py: "python",
  // Text / docs
  txt: "text",
  md: "text",
  qmd: "text",
  log: "text",
  // Images
  png: "image",
  jpg: "image",
  jpeg: "image",
  gif: "image",
  svg: "image",
  webp: "image",
  // Data / spreadsheets
  csv: "data",
  parquet: "data",
  arrow: "data",
  xlsx: "data",
  // JSON
  json: "json",
  // Code
  js: "code",
  ts: "code",
  tsx: "code",
  html: "code",
  css: "code",
  toml: "code",
  yaml: "code",
  yml: "code",
  wasm: "code",
  // Audio
  mp3: "audio",
  m4a: "audio",
  ogg: "audio",
  wav: "audio",
  // Video
  mp4: "video",
  m4v: "video",
  mpeg: "video",
  webm: "video",
  mkv: "video",
  // PDF
  pdf: "pdf",
  // Archives
  zip: "zip",
  tar: "zip",
  gz: "zip",
};

export function guessFileIconType(name: string): FileIconType {
  const ext = name.split(".").pop()?.toLowerCase();
  if (!ext) {
    return "unknown";
  }
  return EXT_TO_TYPE[ext] ?? "unknown";
}

export const FILE_ICON: Record<FileIconType, LucideIcon> = {
  directory: FolderIcon,
  python: FileCodeIcon,
  code: FileCodeIcon,
  json: FileJsonIcon,
  text: FileTextIcon,
  image: ImageIcon,
  audio: FileAudioIcon,
  video: FileVideoIcon,
  data: FileSpreadsheetIcon,
  pdf: FileTextIcon,
  zip: FolderArchiveIcon,
  unknown: FileIcon,
};

export const FILE_ICON_COLOR: Record<FileIconType, string> = {
  directory: "text-amber-500",
  python: "text-blue-500",
  code: "text-blue-500",
  json: "text-blue-500",
  text: "text-muted-foreground",
  image: "text-purple-500",
  audio: "text-orange-500",
  video: "text-orange-500",
  data: "text-green-500",
  pdf: "text-red-500",
  zip: "text-muted-foreground",
  unknown: "text-muted-foreground",
};

/**
 * Render a colored file-type icon for a given filename.
 * Pass `className` to control size (defaults to `h-3.5 w-3.5`).
 */
export function renderFileIcon(
  name: string,
  className?: string,
): React.ReactNode {
  const type = guessFileIconType(name);
  const Icon = FILE_ICON[type];
  const color = FILE_ICON_COLOR[type];
  return <Icon className={cn("h-3.5 w-3.5 shrink-0", color, className)} />;
}
