/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react/jsx-no-comment-textnodes */
/* eslint-disable react/jsx-no-target-blank */

import { isStaticNotebook } from "@/core/static/static-state";
import React from "react";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";
import { getMarimoCode } from "@/core/dom/marimo-tag";
import { downloadBlob } from "@/utils/download";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import {
  DialogHeader,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { CopyIcon, DownloadIcon } from "lucide-react";
import { createShareableLink } from "@/core/pyodide/share";

export const StaticBanner: React.FC = () => {
  if (!isStaticNotebook()) {
    return null;
  }

  return (
    <div className="px-4 py-2 bg-[var(--sky-2)] border-b border-[var(--sky-7)] text-md text-[var(--sky-11)] font-semibold flex justify-between items-center gap-4">
      <span>
        This is a static Python notebook built using{" "}
        <a
          href="https://github.com/marimo-team/marimo"
          target="_blank"
          className="underline"
        >
          marimo
        </a>
        .
        <br />
        Some interactive features may not work, see ways to run or edit this.
      </span>
      <span className="flex-shrink-0">
        <StaticBannerDialog />
      </span>
    </div>
  );
};

const StaticBannerDialog = () => {
  let filename = getFilenameFromDOM() || "notebook.py";
  // Trim the path
  const lastSlash = filename.lastIndexOf("/");
  if (lastSlash !== -1) {
    filename = filename.slice(lastSlash + 1);
  }

  const href = window.location.href;
  const code = getMarimoCode();
  const wasmLink = createShareableLink({ code });

  return (
    <Dialog>
      <DialogTrigger asChild={true}>
        <Button variant="secondary">Run or edit this notebook</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{filename}</DialogTitle>
          <DialogDescription className="pt-4 text-md text-left">
            This is a static notebook built using{" "}
            <a
              href="https://github.com/marimo-team/marimo"
              target="_blank"
              className="text-link hover:underline"
            >
              marimo
            </a>
            . marimo is an open-source next-generation Python notebook.
            <hr className="my-3" />
            In order to edit this notebook, you will need to download the code
            locally, install marimo, and run the following in your terminal:
            <div className="font-mono text-sm bg-[var(--sky-2)] rounded-md my-3 p-2 border border-[var(--sky-7)]">
              pip install marimo
              <br />
              marimo edit {filename}
            </div>
            {!href.endsWith(".html") && (
              <>
                or
                <div className="font-mono text-sm bg-[var(--sky-2)] rounded-md my-3 p-2 border border-[var(--sky-7)] break-all">
                  marimo edit {window.location.href}
                </div>
              </>
            )}
            <hr className="my-3" />
            You may also be able to run this notebook entirely in the browser
            via WebAssembly at:{" "}
            <a
              href={wasmLink}
              target="_blank"
              className="text-link hover:underline"
            >
              {wasmLink.slice(0, 40)}...
            </a>
            <br />
            <div className="text-sm text-muted-foreground pt-2">
              <strong>Note:</strong> This feature is experimental and may not
              work for all notebooks. Additionally, some dependencies may not be
              available in the browser.
            </div>
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-4 flex-wrap">
          <Button
            variant="secondary"
            onClick={() => {
              window.navigator.clipboard.writeText(code);
              toast({ title: "Copied to clipboard" });
            }}
          >
            <CopyIcon className="w-4 h-4 mr-1" />
            Copy code
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              downloadBlob(new Blob([code], { type: "text/plain" }), filename);
            }}
          >
            <DownloadIcon className="w-4 h-4 mr-1" />
            Download code
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
