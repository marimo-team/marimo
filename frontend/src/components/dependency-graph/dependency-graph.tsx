/* Copyright 2026 Marimo. All rights reserved. */

import { type Atom, atom, useAtom } from "jotai";

import React from "react";
import { ReactFlowProvider } from "reactflow";
import type { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import type { Variables } from "@/core/variables/types";
import { DependencyGraphTree } from "./dependency-graph-tree";
import { GraphToolbar } from "./panels";
import type { GraphSettings, LayoutDirection } from "./types";

import "reactflow/dist/style.css";
import "./dependency-graph.css";

interface Props {
  cellIds: CellId[];
  variables: Variables;
  cellAtoms: Atom<CellData>[];
  children?: React.ReactNode;
}

const graphViewAtom = atom<LayoutDirection>("TB");
const graphViewSettings = atom<GraphSettings>({
  hidePureMarkdown: true,
  hideReusableFunctions: false,
});

export const DependencyGraph: React.FC<Props> = (props) => {
  const [layoutDirection, setLayoutDirection] = useAtom(graphViewAtom);
  const [settings, setSettings] = useAtom(graphViewSettings);

  return (
    <ReactFlowProvider key={layoutDirection}>
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
    </ReactFlowProvider>
  );
};
