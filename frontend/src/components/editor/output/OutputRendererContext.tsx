/* Copyright 2026 Marimo. All rights reserved. */
import React, { createContext, useContext } from "react";
import type { OutputMessage } from "@/core/kernel/messages";
import type { CellId } from "@/core/cells/ids";

export interface OutputRendererProps {
  message: Pick<OutputMessage, "channel" | "data" | "mimetype">;
  cellId?: CellId;
  onRefactorWithAI?: (opts: {
    prompt: string;
    triggerImmediately: boolean;
  }) => void;
  wrapText?: boolean;
  metadata?: { width?: number; height?: number };
  renderFallback?: (mimetype: string) => React.ReactNode;
}

export type OutputRendererComponent = React.FC<OutputRendererProps>;

export const OutputRendererContext =
  createContext<OutputRendererComponent | null>(null);

export const useOutputRenderer = () => {
  return useContext(OutputRendererContext);
};
