/* Copyright 2024 Marimo. All rights reserved. */
import { ReactFlowProvider } from "reactflow";

import React from "react";
import type { Variables } from "@/core/variables/types";
import type { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import { type Atom, atom, useAtom } from "jotai";

import type { GraphLayoutView, GraphSettings } from "./types";
import { DependencyGraphMinimap } from "./dependency-graph-minimap";
import { GraphToolbar } from "./panels";
import { DependencyGraphTree } from "./dependency-graph-tree";

import "reactflow/dist/style.css";
import "./dependency-graph.css";

interface Props {
  cellIds: CellId[];
  variables: Variables;
  cellAtoms: Array<Atom<CellData>>;
  children?: React.ReactNode;
}

const graphViewAtom = atom<GraphLayoutView>("_minimap_");
const graphViewSettings = atom<GraphSettings>({
  hidePureMarkdown: true,
});

export const DependencyGraph: React.FC<Props> = (props) => {
  const [layoutDirection, setLayoutDirection] = useAtom(graphViewAtom);
  const [settings, setSettings] = useAtom(graphViewSettings);

  const renderGraph = () => {
    if (layoutDirection === "_minimap_") {
      return (
        <DependencyGraphMinimap {...props}>
          <GraphToolbar
            settings={settings}
            onSettingsChange={setSettings}
            view={layoutDirection}
            onChange={setLayoutDirection}
          />
        </DependencyGraphMinimap>
      );
    }
    return (
      <DependencyGraphTree
        {...props}
        settings={settings}
        layoutDirection={layoutDirection}
      >
        <GraphToolbar
          settings={settings}
          onSettingsChange={setSettings}
          view={layoutDirection}
          onChange={setLayoutDirection}
        />
      </DependencyGraphTree>
    );
  };

  return (
    <ReactFlowProvider key={layoutDirection}>{renderGraph()}</ReactFlowProvider>
  );
};
