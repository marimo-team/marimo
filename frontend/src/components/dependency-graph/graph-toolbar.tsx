/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo } from "react";
import { Panel } from "reactflow";
import { Button } from "../ui/button";
import { Rows3Icon, NetworkIcon } from "lucide-react";
import { GraphLayoutView } from "./types";

interface Props {
  view: GraphLayoutView;
  onChange: (view: GraphLayoutView) => void;
}

export const GraphToolbar: React.FC<Props> = memo(({ onChange, view }) => {
  return (
    <Panel position="top-right" className="space-x-2">
      <Button
        variant="outline"
        className="bg-background"
        aria-selected={view === "_minimap_"}
        size="xs"
        onClick={() => onChange("_minimap_")}
      >
        <Rows3Icon className="w-4 h-4 mr-1" />
        Mini Map
      </Button>
      <Button
        variant="outline"
        className="bg-background"
        aria-selected={view === "TB"}
        size="xs"
        onClick={() => onChange("TB")}
      >
        <NetworkIcon className="w-4 h-4 mr-1" />
        Vertical Tree
      </Button>
      <Button
        variant="outline"
        className="bg-background"
        aria-selected={view === "LR"}
        size="xs"
        onClick={() => onChange("LR")}
      >
        <NetworkIcon className="w-4 h-4 mr-1 transform -rotate-90" /> Horizontal
        Tree
      </Button>
    </Panel>
  );
});
GraphToolbar.displayName = "GraphToolbar";
