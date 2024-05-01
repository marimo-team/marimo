/* Copyright 2024 Marimo. All rights reserved. */
import { ReactFlowProvider } from "reactflow";

import React from "react";
import { Variables } from "@/core/variables/types";
import { CellId } from "@/core/cells/ids";
import { CellData } from "@/core/cells/types";
import { Atom, atom, useAtom } from "jotai";

import { GraphLayoutView } from "./types";
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

export const DependencyGraph: React.FC<Props> = (props) => {
  const [layoutDirection, setLayoutDirection] = useAtom(graphViewAtom);

  const renderGraph = () => {
    if (layoutDirection === "_minimap_") {
      return (
        <DependencyGraphMinimap {...props}>
          <GraphToolbar view={layoutDirection} onChange={setLayoutDirection} />
        </DependencyGraphMinimap>
      );
    }
    return (
      <DependencyGraphTree {...props} layoutDirection={layoutDirection}>
        <GraphToolbar view={layoutDirection} onChange={setLayoutDirection} />
      </DependencyGraphTree>
    );
  };

  return (
    <ReactFlowProvider key={layoutDirection}>{renderGraph()}</ReactFlowProvider>
  );
};
