/* Copyright 2024 Marimo. All rights reserved. */

import { ReactFlowProvider } from "@xyflow/react";
import React, { memo } from "react";
import { StartupLogsAlert } from "../../alerts/startup-logs-alert";
import { PackageAlert } from "../../package-alert";
import { StdinBlockingAlert } from "../../stdin-blocking-alert";
import type { ICellRendererProps } from "../types";
import { Canvas } from "./components/canvas";
import type { CanvasLayout } from "./types";

/**
 * Canvas layout renderer
 * Provides a free-form canvas using react-flow where cells can be positioned anywhere
 */
const CanvasLayoutRendererComponent: React.FC<
  ICellRendererProps<CanvasLayout>
> = (props) => {
  return (
    <>
      <PackageAlert />
      <StartupLogsAlert />
      <StdinBlockingAlert />
      <ReactFlowProvider>
        <Canvas {...props} />
      </ReactFlowProvider>
    </>
  );
};

export const CanvasLayoutRenderer = memo(CanvasLayoutRendererComponent);
CanvasLayoutRenderer.displayName = "CanvasLayoutRenderer";
