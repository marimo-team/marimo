/* Copyright 2026 Marimo. All rights reserved. */

import type { WritableAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { store } from "@/core/state/jotai";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

export type SessionPanelSection = "variables" | "datasources";
export type FileExplorerPanelSection = "files" | "remote-storage";

export interface PanelAccordionState<Section extends string> {
  openSections: Section[];
  hasUserInteracted: boolean;
}

export const sessionPanelAtom = atomWithStorage<
  PanelAccordionState<SessionPanelSection>
>(
  "marimo:session-panel:state",
  { openSections: ["variables"], hasUserInteracted: false },
  jotaiJsonStorage,
);

export const fileExplorerPanelAtom = atomWithStorage<
  PanelAccordionState<FileExplorerPanelSection>
>(
  "marimo:file-explorer-panel:state",
  { openSections: ["files"], hasUserInteracted: false },
  jotaiJsonStorage,
);

/**
 * Expand an accordion section without collapsing others. Leaves
 * `hasUserInteracted` untouched so auto-open heuristics are unaffected.
 */
export function expandAccordionSection<Section extends string>(
  panelAtom: WritableAtom<
    PanelAccordionState<Section>,
    [(prev: PanelAccordionState<Section>) => PanelAccordionState<Section>],
    void
  >,
  section: Section,
): void {
  store.set(panelAtom, (prev) =>
    prev.openSections.includes(section)
      ? prev
      : { ...prev, openSections: [...prev.openSections, section] },
  );
}
