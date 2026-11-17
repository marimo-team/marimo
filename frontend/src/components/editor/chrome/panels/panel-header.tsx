/* Copyright 2026 Marimo. All rights reserved. */

import { createContext, useContext, type PropsWithChildren } from "react";
import { createPortal } from "react-dom";

export const PanelHeaderActionsContext = createContext<HTMLElement | null>(
  null,
);

export function PanelHeaderActions({ children }: PropsWithChildren) {
  const target = useContext(PanelHeaderActionsContext);
  return target ? createPortal(children, target) : children;
}
