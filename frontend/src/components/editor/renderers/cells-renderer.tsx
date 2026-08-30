/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import type React from "react";
import { memo, type PropsWithChildren } from "react";
import { flattenTopLevelNotebookCells, useNotebook } from "@/core/cells/cells";
import type { AppConfig } from "@/core/config/config-schema";
import { KnownQueryParams } from "@/core/constants";
import { useLayoutActions, useLayoutState } from "@/core/layout/layout";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { logNever } from "@/utils/assertNever";
import { getCellRendererPlugin, type LayoutDataByType } from "./plugins";
import { type LayoutType, OVERRIDABLE_LAYOUT_TYPES } from "./types";

interface Props {
  appConfig: AppConfig;
  mode: AppMode;
}

export const CellsRenderer: React.FC<PropsWithChildren<Props>> = memo(
  ({ appConfig, mode, children }) => {
    const { selectedLayout, layoutData } = useLayoutState();
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
    let finalLayout = selectedLayout;
    const params = new URLSearchParams(window.location.search);
    if (mode === "read" && params.has(KnownQueryParams.viewAs)) {
      const viewAsOverride = params.get(KnownQueryParams.viewAs);
      if (OVERRIDABLE_LAYOUT_TYPES.includes(viewAsOverride as LayoutType)) {
        finalLayout = viewAsOverride as LayoutType;
      }
    }

    return (
      <PluginCellRenderer
        appConfig={appConfig}
        mode={mode}
        finalLayout={finalLayout}
        layoutData={layoutData}
      />
    );
  },
);
CellsRenderer.displayName = "CellsRenderer";

interface PluginCellRendererProps extends PropsWithChildren<Props> {
  appConfig: AppConfig;
  mode: AppMode;
  layoutData: Partial<LayoutDataByType>;
  finalLayout: LayoutType;
}

export const PluginCellRenderer = (props: PluginCellRendererProps) => {
  const { appConfig, mode, layoutData, finalLayout } = props;
  const notebook = useNotebook();
  const { setCurrentLayoutData } = useLayoutActions();
  const cells = flattenTopLevelNotebookCells(notebook);

  const renderFor = <K extends LayoutType>(
    type: K,
    data: LayoutDataByType[K] | undefined,
  ) => {
    const plugin = getCellRendererPlugin(type);
    const Renderer = plugin.Component;
    return (
      <Renderer
        appConfig={appConfig}
        mode={mode}
        cells={cells}
        layout={data ?? plugin.getInitialLayout(cells)}
        setLayout={setCurrentLayoutData}
      />
    );
  };

  switch (finalLayout) {
    case "vertical":
      return renderFor("vertical", layoutData.vertical);
    case "grid":
      return renderFor("grid", layoutData.grid);
    case "slides":
      return renderFor("slides", layoutData.slides);
    default:
      logNever(finalLayout);
      return null;
  }
};
