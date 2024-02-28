/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import useResizeObserver from "use-resize-observer";
import { FileExplorer } from "../../file-tree/file-explorer";
import { cn } from "@/utils/cn";
import { useFileExplorerUpload } from "../../file-tree/upload";

export const FileExplorerPanel: React.FC = () => {
  const { ref, height = 1 } = useResizeObserver<HTMLDivElement>();
  const { getRootProps, getInputProps, isDragActive } = useFileExplorerUpload({
    noClick: true,
    noKeyboard: true,
  });

  return (
    <div
      {...getRootProps()}
      className={cn("flex flex-col flex-1 overflow-hidden relative")}
    >
      <input {...getInputProps()} />
      {isDragActive && (
        <div className="absolute inset-0 flex items-center uppercase justify-center text-xl font-bold text-primary/90 bg-accent/85 z-10 border-2 border-dashed border-primary/90 rounded-lg pointer-events-none">
          Drop files here
        </div>
      )}

      <div ref={ref} className="flex flex-col flex-1 overflow-hidden">
        <FileExplorer height={height} />
      </div>
    </div>
  );
};
