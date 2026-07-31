/* Copyright 2026 Marimo. All rights reserved. */

import type { LucideIcon } from "lucide-react";
import { BookPlusIcon, FileSymlink } from "lucide-react";
import type { StorageEntry, StorageNamespace } from "@/core/storage/types";

type BackendType = StorageNamespace["backendType"];

export interface StorageSnippetContext {
  variableName: string;
  protocol: string;
  entry: StorageEntry;
  backendType: BackendType;
}

export interface StorageSnippet {
  id: string;
  label: string;
  icon: LucideIcon;
  /** Return the code string, or null to hide the snippet for this context. */
  getCode: (ctx: StorageSnippetContext) => string | null;
}

const NOT_SIGNABLE_PROTOCOLS = new Set(["http", "file", "in-memory"]);

function escapeForPythonString(value: string): string {
  return JSON.stringify(value).slice(1, -1);
}

interface ParsedHfRepoPath {
  repoType: "model" | "dataset" | "space";
  repoId: string;
  filename: string;
}

function parseHfRepoPath(path: string): ParsedHfRepoPath | null {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "datasets" && parts.length >= 4) {
    return {
      repoType: "dataset",
      repoId: `${parts[1]}/${parts[2]}`,
      filename: parts.slice(3).join("/"),
    };
  }
  if (parts[0] === "spaces" && parts.length >= 4) {
    return {
      repoType: "space",
      repoId: `${parts[1]}/${parts[2]}`,
      filename: parts.slice(3).join("/"),
    };
  }
  if (parts.length >= 3 && parts[0] !== "buckets") {
    return {
      repoType: "model",
      repoId: `${parts[0]}/${parts[1]}`,
      filename: parts.slice(2).join("/"),
    };
  }
  return null;
}

function hfHubDownloadSnippet(parsed: ParsedHfRepoPath): string {
  const repoId = escapeForPythonString(parsed.repoId);
  const filename = escapeForPythonString(parsed.filename);
  const repoType = escapeForPythonString(parsed.repoType);
  return `from huggingface_hub import hf_hub_download\n\nlocal_path = hf_hub_download(\n    repo_id="${repoId}",\n    filename="${filename}",\n    repo_type="${repoType}",\n)`;
}

export const STORAGE_SNIPPETS: StorageSnippet[] = [
  {
    id: "read-file",
    label: "Insert read snippet",
    icon: BookPlusIcon,
    getCode: (ctx) => {
      if (ctx.entry.kind === "directory") {
        return null;
      }
      const path = escapeForPythonString(ctx.entry.path);
      if (ctx.backendType === "huggingface") {
        const parsed = parseHfRepoPath(ctx.entry.path);
        if (!parsed) {
          return null;
        }
        return `${hfHubDownloadSnippet(parsed)}\n\nwith open(local_path, "rb") as f:\n    _data = f.read()\n_data`;
      }
      if (ctx.backendType === "obstore") {
        return `_data = ${ctx.variableName}.get("${path}").bytes()\n_data`;
      }
      return `_data = ${ctx.variableName}.cat_file("${path}")\n_data`;
    },
  },
  {
    id: "download-file",
    label: "Insert download snippet",
    icon: FileSymlink,
    getCode: (ctx) => {
      if (ctx.entry.kind === "directory") {
        return null;
      }
      const path = escapeForPythonString(ctx.entry.path);
      if (ctx.backendType === "huggingface") {
        const parsed = parseHfRepoPath(ctx.entry.path);
        if (!parsed) {
          return null;
        }
        return `${hfHubDownloadSnippet(parsed)}\nlocal_path`;
      }
      if (ctx.backendType === "obstore") {
        if (NOT_SIGNABLE_PROTOCOLS.has(ctx.protocol)) {
          return null;
        }
        return `from datetime import timedelta\nfrom obstore import sign\n\nsigned_url = sign(\n    ${ctx.variableName}, "GET", "${path}",\n    expires_in=timedelta(hours=1),\n)\nsigned_url`;
      }
      const filename = escapeForPythonString(
        ctx.entry.path.split("/").pop() || "download",
      );
      return `${ctx.variableName}.get("${path}", "${filename}")`;
    },
  },
];
