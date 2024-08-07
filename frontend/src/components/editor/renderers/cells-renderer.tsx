/* Copyright 2024 Marimo. All rights reserved. */
import { flattenTopLevelNotebookCells, useNotebook } from "@/core/cells/cells";
import React, { PropsWithChildren, memo } from "react";
import { cellRendererPlugins } from "./plugins";
import { AppConfig } from "@/core/config/config-schema";
import { AppMode, kioskModeAtom } from "@/core/mode";
import { useLayoutActions, useLayoutState } from "@/core/layout/layout";
import { useAtomValue } from "jotai";

interface Props {
  appConfig: AppConfig;
  mode: AppMode;
}

export const CellsRenderer: React.FC<PropsWithChildren<Props>> = memo(
  ({ appConfig, mode, children }) => {
    const notebook = useNotebook();
    const { selectedLayout, layoutData } = useLayoutState();
    const { setCurrentLayoutData } = useLayoutActions();
    const kioskMode = useAtomValue(kioskModeAtom);

    // Just render children if we are in edit mode
    if (mode === "edit" && !kioskMode) {
      return children;
    }

    const plugin = cellRendererPlugins.find((p) => p.type === selectedLayout);

    // Just render children if there is no plugin
    if (!plugin) {
      return children;
    }

    const cells = flattenTopLevelNotebookCells(notebook);

    const Renderer = plugin.Component;
    const body = (
      <Renderer
        appConfig={appConfig}
        mode={mode}
        cells={cells}
        layout={layoutData[selectedLayout] || plugin.getInitialLayout(cells)}
        setLayout={setCurrentLayoutData}
      />
    );

    return body;
  },
);
CellsRenderer.displayName = "CellsRenderer";
