/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react/jsx-no-comment-textnodes */
/* eslint-disable react/jsx-no-target-blank */

import { isStaticNotebook } from "@/core/static/static-state";
import type React from "react";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";
import { downloadBlob } from "@/utils/download";
import {
  DialogHeader,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { CopyIcon, DownloadIcon } from "lucide-react";
import { createShareableLink } from "@/core/wasm/share";
import { copyToClipboard } from "@/utils/copy";
import { Constants } from "@/core/constants";
import { useFilename } from "@/core/saving/filename";
import { useAtomValue } from "jotai";
import { codeAtom } from "@/core/saving/file-state";

export const StaticBanner: React.FC = () => {
  const code = useAtomValue(codeAtom);

  if (!isStaticNotebook()) {
    return null;
  }

  if (!code) {
    return null;
  }

  return (
    <div
      className="px-4 py-2 bg-[var(--sky-2)] border-b border-[var(--sky-7)] text-[var(--sky-11)] flex justify-between items-center gap-4 no-print text-sm"
      data-testid="static-notebook-banner"
    >
      <span>
        Static{" "}
        <a
          href={Constants.githubPage}
          target="_blank"
          className="text-[var(--sky-11)] font-medium underline"
        >
          marimo
        </a>{" "}
        notebook - Run or edit for full interactivity
      </span>
      <span className="flex-shrink-0">
        <StaticBannerDialog code={code} />
      </span>
    </div>
  );
};

const StaticBannerDialog = ({ code }: { code: string }) => {
  let filename = useFilename() || "notebook.py";
  // Trim the path
  const lastSlash = filename.lastIndexOf("/");
  if (lastSlash !== -1) {
    filename = filename.slice(lastSlash + 1);
  }

  const href = window.location.href;
  const wasmLink = createShareableLink({ code });

  return (
    <Dialog>
      <DialogTrigger asChild={true}>
        <Button
          data-testid="static-notebook-dialog-trigger"
          variant="outline"
          size="xs"
        >
          Run or Edit
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{filename}</DialogTitle>
          <DialogDescription className="pt-3 text-left space-y-3">
            <p>
              This is a static{" "}
              <a
                href={Constants.githubPage}
                target="_blank"
                className="text-[var(--sky-11)] hover:underline font-medium"
              >
                marimo
              </a>{" "}
              notebook. To run interactively:
            </p>

            <div className="rounded-lg p-3 border bg-[var(--sky-2)] border-[var(--sky-7)]">
              <div className="font-mono text-[var(--sky-11)] leading-relaxed">
                pip install marimo
                <br />
                marimo edit {filename}
              </div>
            </div>

            {!href.endsWith(".html") && (
              <div className="rounded-lg p-3 border bg-[var(--sky-2)] border-[var(--sky-7)]">
                <div className="text-sm text-[var(--sky-12)] mb-1">
                  Or run directly from URL:
                </div>
                <div className="font-mono text-[var(--sky-11)] break-all">
                  marimo edit {window.location.href}
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-[var(--sky-7)]">
              <p className="text-sm text-[var(--sky-12)] mb-2">
                <strong>Try in browser with WebAssembly:</strong>{" "}
                <a
                  href={wasmLink}
                  target="_blank"
                  className="text-[var(--sky-11)] hover:underline break-all"
                  rel="noreferrer"
                >
                  {wasmLink.slice(0, 50)}...
                </a>
              </p>
              <p className="text-sm text-[var(--sky-12)]">
                Note: WebAssembly may not work for all notebooks. Additionally,
                some dependencies may not be available in the browser.
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-3 pt-2">
          <Button
            data-testid="copy-static-notebook-dialog-button"
            variant="outline"
            size="sm"
            onClick={async () => {
              await copyToClipboard(code);
              toast({ title: "Copied to clipboard" });
            }}
          >
            <CopyIcon className="w-3 h-3 mr-2" />
            Copy code
          </Button>
          <Button
            data-testid="download-static-notebook-dialog-button"
            variant="outline"
            size="sm"
            onClick={() => {
              downloadBlob(new Blob([code], { type: "text/plain" }), filename);
            }}
          >
            <DownloadIcon className="w-3 h-3 mr-2" />
            Download
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
