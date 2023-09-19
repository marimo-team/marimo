/* Copyright 2023 Marimo. All rights reserved. */
import { useCells } from "@/core/state/cells";
import React, { PropsWithChildren, memo } from "react";
import { cellRendererPlugins } from "./plugins";
import { AppConfig } from "@/core/config/config";
import { AppMode } from "@/core/mode";
import { layoutDataAtom, layoutViewAtom } from "@/core/state/layout";
import { useAtom } from "jotai";

interface Props {
  appConfig: AppConfig;
  mode: AppMode;
}

export const CellsRenderer: React.FC<PropsWithChildren<Props>> = memo(
  ({ appConfig, mode, children }) => {
    const cells = useCells();
    const [layoutData, setLayoutData] = useAtom(layoutDataAtom);
    const [layoutType] = useAtom(layoutViewAtom);

    // Just render children if we are in edit mode
    if (mode === "edit") {
      return children;
    }

    const plugin = cellRendererPlugins.find((p) => p.type === layoutType);

    // Just render children if there is no plugin
    if (!plugin) {
      return children;
    }

    const Renderer = plugin.Component;
    const body = (
      <Renderer
        appConfig={appConfig}
        mode={mode}
        cells={cells.present}
        layout={layoutData || plugin.getInitialLayout(cells.present)}
        setLayout={setLayoutData}
      />
    );

    return body;
  }
);
CellsRenderer.displayName = "CellsRenderer";
