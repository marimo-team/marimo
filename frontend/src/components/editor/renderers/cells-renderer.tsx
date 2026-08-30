/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type React from "react";
import { memo, type PropsWithChildren } from "react";
import { flattenTopLevelNotebookCells, useNotebook } from "@/core/cells/cells";
import type { AppConfig } from "@/core/config/config-schema";
import {
  type LayoutState,
  resolveLayoutData,
  resolveLayoutType,
  useLayoutActions,
  useLayoutState,
} from "@/core/layout/layout";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { cellRendererPlugins } from "./plugins";
import type { ICellRendererPlugin } from "./types";

interface Props {
  appConfig: AppConfig;
  mode: AppMode;
}

export const CellsRenderer: React.FC<PropsWithChildren<Props>> = memo(
  ({ appConfig, mode, children }) => {
    const layoutState = useLayoutState();
    const { selectedLayout } = layoutState;
    const kioskMode = useAtomValue(kioskModeAtom);

    // Render children (the editable notebook) in edit mode, and in present
    // mode with the vertical layout: keeping the same tree across the
    // edit<->present toggle preserves cell output DOM (iframes, widgets).
    // Grid/slides layouts and kiosk mode swap to their layout renderer.
    if (
      !kioskMode &&
      (mode === "edit" || (mode === "present" && selectedLayout === "vertical"))
    ) {
      return children;
    }

    // We allow overriding the layout type by url params when in 'read' mode,
    // for example, forcing the 'slides' view.
    // https://marimo.app/?slug=14ovyr8&mode=run&view-as=slides
    const finalLayout = resolveLayoutType({
      selectedLayout,
      isReading: mode === "read",
      searchParams: new URLSearchParams(window.location.search),
    });

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
        layoutState={layoutState}
      />
    );
  },
);
CellsRenderer.displayName = "CellsRenderer";

interface PluginCellRendererProps extends PropsWithChildren<Props> {
  appConfig: AppConfig;
  mode: AppMode;
  // oxlint-disable-next-line typescript/no-explicit-any
  plugin: ICellRendererPlugin<any, any>;
  layoutState: LayoutState;
}

export const PluginCellRenderer = (props: PluginCellRendererProps) => {
  const { appConfig, mode, plugin, layoutState } = props;
  const notebook = useNotebook();
  const { setCurrentLayoutData } = useLayoutActions();
  const cells = flattenTopLevelNotebookCells(notebook);
  const layout = resolveLayoutData({ state: layoutState, plugin, cells });

  const Renderer = plugin.Component;
  const body = (
    <Renderer
      appConfig={appConfig}
      mode={mode}
      cells={cells}
      layout={layout}
      setLayout={setCurrentLayoutData}
    />
  );

  return body;
};
