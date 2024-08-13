/* Copyright 2024 Marimo. All rights reserved. */
import { flattenTopLevelNotebookCells, useNotebook } from "@/core/cells/cells";
import type React from "react";
import { type PropsWithChildren, memo } from "react";
import { cellRendererPlugins } from "./plugins";
import type { AppConfig } from "@/core/config/config-schema";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { useLayoutActions, useLayoutState } from "@/core/layout/layout";
import { useAtomValue } from "jotai";
import { KnownQueryParams } from "@/core/constants";
import { type LayoutType, OVERRIDABLE_LAYOUT_TYPES } from "./types";

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

    // We allow overriding the layout type by url params when in 'read' mode,
    // for example, forcing the 'slides' view.
    // https://marimo.app/?slug=14ovyr8&mode=run&view-as=slides
    let finalLayout = selectedLayout;
    const params = new URLSearchParams(window.location.search);
    if (mode === "read" && params.has(KnownQueryParams.viewAs)) {
      const viewAsOverride = params.get(KnownQueryParams.viewAs);
      if (OVERRIDABLE_LAYOUT_TYPES.includes(viewAsOverride as LayoutType)) {
        finalLayout = viewAsOverride as LayoutType;
      }
    }

    const plugin = cellRendererPlugins.find((p) => p.type === finalLayout);

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
        layout={layoutData[finalLayout] || plugin.getInitialLayout(cells)}
        setLayout={setCurrentLayoutData}
      />
    );

    return body;
  },
);
CellsRenderer.displayName = "CellsRenderer";
