/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import useResizeObserver from "use-resize-observer";
import { FileExplorer } from "../../file-tree/file-explorer";

export const FileExplorerPanel: React.FC = () => {
  const { ref, height = 1 } = useResizeObserver<HTMLDivElement>();
  return (
    <div ref={ref} className="flex flex-col flex-1 overflow-hidden">
      <FileExplorer height={height} />
    </div>
  );
};
