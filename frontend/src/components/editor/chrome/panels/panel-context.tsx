/* Copyright 2026 Marimo. All rights reserved. */

import { createContext, useContext } from "react";
import { invariant } from "@/utils/invariant";

export type PanelSection = "sidebar" | "developer-panel";

const PanelSectionContext = createContext<PanelSection | null>(null);

export const PanelSectionProvider = PanelSectionContext.Provider;

/**
 * Hook to get the current panel section context.
 * Returns "sidebar" or "developer-panel" depending on where the panel is rendered.
 * Throws if used outside of a panel context.
 */
export function usePanelSection(): PanelSection {
  const section = useContext(PanelSectionContext);
  invariant(
    section !== null,
    "usePanelSection must be used within a PanelSectionProvider",
  );
  return section;
}

/**
 * Hook to get the preferred orientation based on the panel section.
 * - Sidebar panels should use vertical layouts (stacked)
 * - Developer panel should use horizontal layouts (side-by-side)
 */
export function usePanelOrientation(): "horizontal" | "vertical" {
  const section = usePanelSection();
  return section === "sidebar" ? "vertical" : "horizontal";
}
