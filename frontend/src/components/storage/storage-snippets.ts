/* Copyright 2026 Marimo. All rights reserved. */

import type { LucideIcon } from "lucide-react";
import { BookOpenIcon, LinkIcon } from "lucide-react";
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
  return value.replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

export const STORAGE_SNIPPETS: StorageSnippet[] = [
  {
    id: "read-file",
    label: "Insert read snippet",
    icon: BookOpenIcon,
    getCode: (ctx) => {
      if (ctx.entry.kind === "directory") {
        return null;
      }
      const path = escapeForPythonString(ctx.entry.path);
      if (ctx.backendType === "obstore") {
        return `_data = ${ctx.variableName}.get("${path}").bytes()\n_data`;
      }
      return `_data = ${ctx.variableName}.cat_file("${path}")\n_data`;
    },
  },
  {
    id: "download-file",
    label: "Insert download snippet",
    icon: LinkIcon,
    getCode: (ctx) => {
      if (ctx.entry.kind === "directory") {
        return null;
      }
      const path = escapeForPythonString(ctx.entry.path);
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
