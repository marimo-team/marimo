/* Copyright 2024 Marimo. All rights reserved. */
import {
  DatabaseIcon,
  FileAudioIcon,
  FileCodeIcon,
  FileIcon,
  FileImageIcon,
  FileJsonIcon,
  FileTextIcon,
  FileVideo2Icon,
  FolderArchiveIcon,
  FolderIcon,
  type LucideIcon,
} from "lucide-react";

/* Copyright 2024 Marimo. All rights reserved. */
export type FileType =
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

export function guessFileType(name: string): FileType {
  const ext = name.split(".").pop();
  if (ext === undefined) {
    return "unknown";
  }
  switch (ext.toLowerCase()) {
    case "py":
      return "python";
    case "txt":
    case "md":
    case "qmd":
      return "text";
    case "png":
    case "jpg":
    case "jpeg":
    case "gif":
      return "image";
    case "csv":
      return "data";
    case "json":
      return "json";
    // Non-exhaustive list of code file extensions
    case "js":
    case "ts":
    case "tsx":
    case "html":
    case "css":
    case "toml":
    case "yaml":
    case "yml":
    case "wasm":
      return "code";
    case "mp3":
    case "m4a":
    case "m4v":
    case "ogg":
    case "wav":
      return "audio";
    case "mp4":
    case "webm":
    case "mkv":
      return "video";
    case "pdf":
      return "pdf";
    case "zip":
    case "tar":
    case "gz":
      return "zip";
    default:
      return "unknown";
  }
}

export const FILE_TYPE_ICONS: Record<FileType, LucideIcon> = {
  directory: FolderIcon,
  python: FileCodeIcon,
  json: FileJsonIcon,
  code: FileCodeIcon,
  text: FileTextIcon,
  image: FileImageIcon,
  audio: FileAudioIcon,
  video: FileVideo2Icon,
  pdf: FileCodeIcon,
  zip: FolderArchiveIcon,
  data: DatabaseIcon,
  unknown: FileIcon,
};

const TAB = "    ";

export const PYTHON_CODE_FOR_FILE_TYPE: Record<
  FileType,
  (path: string) => string
> = {
  directory: (path) => `os.listdir("${path}")`,
  python: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  json: (path) =>
    `with open("${path}", "r") as _f:\n${TAB}_data = json.load(_f)\n`,
  code: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  text: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  image: (path) => `mo.image("${path}")`,
  audio: (path) => `mo.audio("${path}")`,
  video: (path) => `mo.video("${path}")`,
  pdf: (path) => `with open("${path}", "rb") as _f:\n${TAB}...\n`,
  zip: (path) => `with open("${path}", "rb") as _f:\n${TAB}...\n`,
  data: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
  unknown: (path) => `with open("${path}", "r") as _f:\n${TAB}...\n`,
};
