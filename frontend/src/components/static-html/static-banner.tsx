/* Copyright 2023 Marimo. All rights reserved. */
import { isStaticNotebook } from "@/core/static/static-state";
import React from "react";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";
import { getMarimoCode } from "@/core/dom/marimo-tag";
import { downloadBlob } from "@/utils/download";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";
import { CopyIcon, DownloadIcon } from "lucide-react";

export const StaticBanner: React.FC = () => {
  if (!isStaticNotebook()) {
    return null;
  }

  return (
    <div className="px-4 py-2 bg-[var(--sky-2)] border-b border-[var(--sky-7)] text-md text-[var(--sky-11)] font-semibold flex justify-between items-center">
      <span>
        This is a static notebook. Some interactive features will not work,
        however you can download the code and run it locally.
      </span>
      <span className="flex flex-wrap justify-end">
        <Button
          className="ml-2 flex-shrink-0"
          variant="secondary"
          size="xs"
          onClick={() => {
            const code = getMarimoCode();
            window.navigator.clipboard.writeText(code);
            toast({ title: "Copied to clipboard" });
          }}
        >
          <CopyIcon className="w-4 h-4 mr-1" />
          Copy code
        </Button>
        <Button
          className="ml-2 flex-shrink-0"
          variant="secondary"
          size="xs"
          onClick={() => {
            const code = getMarimoCode();
            downloadBlob(
              new Blob([code], { type: "text/plain" }),
              getFilenameFromDOM() || "app.py"
            );
          }}
        >
          <DownloadIcon className="w-4 h-4 mr-1" />
          Download code
        </Button>
      </span>
    </div>
  );
};
