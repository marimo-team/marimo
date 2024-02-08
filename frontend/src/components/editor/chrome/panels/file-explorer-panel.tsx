/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import useResizeObserver from "use-resize-observer";
import { FileExplorer } from "../../file-tree/file-explorer";

export const FileExplorerPanel: React.FC = (props) => {
  const { ref, height = 1 } = useResizeObserver<HTMLDivElement>();

  return (
    <div ref={ref} className="h-full">
      <div id="noop-dnd-container" />
      <FileExplorer height={height} />
    </div>
  );
};
