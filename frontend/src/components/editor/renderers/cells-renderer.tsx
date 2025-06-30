/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type React from "react";
import { memo, type PropsWithChildren } from "react";
import { flattenTopLevelNotebookCells, useNotebook } from "@/core/cells/cells";
import type { AppConfig } from "@/core/config/config-schema";
import { KnownQueryParams } from "@/core/constants";
import {
  type LayoutData,
  useLayoutActions,
  useLayoutState,
} from "@/core/layout/layout";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { cellRendererPlugins } from "./plugins";
import {
  type ICellRendererPlugin,
  type LayoutType,
  OVERRIDABLE_LAYOUT_TYPES,
} from "./types";

interface Props {
  appConfig: AppConfig;
  mode: AppMode;
}

export const CellsRenderer: React.FC<PropsWithChildren<Props>> = memo(
  ({ appConfig, mode, children }) => {
    const { selectedLayout, layoutData } = useLayoutState();
    const kioskMode = useAtomValue(kioskModeAtom);

    // Just render children if we are in edit mode
    if (mode === "edit" && !kioskMode) {
      return children;
    }

    // We allow overriding the layout type by url params when in 'read' mode,
    // for example, forcing the 'slides' view.
    // https://marimo.app/?slug=14ovyr8&mode=run&view-as=slides
    let finalLayout = selectedLayout;
    const params = new URLSearchParams(globalThis.location.search);
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

    return (
      <PluginCellRenderer
        appConfig={appConfig}
        mode={mode}
        plugin={plugin}
        layoutData={layoutData}
        finalLayout={finalLayout}
      />
    );
  },
);
CellsRenderer.displayName = "CellsRenderer";

interface PluginCellRendererProps extends PropsWithChildren<Props> {
  appConfig: AppConfig;
  mode: AppMode;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plugin: ICellRendererPlugin<any, any>;
  layoutData: Partial<Record<LayoutType, LayoutData>>;
  finalLayout: LayoutType;
}

export const PluginCellRenderer = (props: PluginCellRendererProps) => {
  const { appConfig, mode, plugin, layoutData, finalLayout } = props;
  const notebook = useNotebook();
  const { setCurrentLayoutData } = useLayoutActions();
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
};
