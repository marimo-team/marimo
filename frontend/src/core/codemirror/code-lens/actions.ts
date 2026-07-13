/* Copyright 2026 Marimo. All rights reserved. */

import {
  expandAccordionSection,
  fileExplorerPanelAtom,
  sessionPanelAtom,
} from "@/components/editor/chrome/panels/panel-accordion-state";
import { openPanel } from "@/components/editor/chrome/state";
import { assertNever } from "@/utils/assertNever";
import type { CodeLensKind } from "./entities";

/**
 * Opens the panel associated with a code lens target, expanding the accordion
 * section that holds it.
 */
export function openLensTarget(kind: CodeLensKind): void {
  switch (kind) {
    case "table":
    case "connection":
      openPanel("variables");
      expandAccordionSection(sessionPanelAtom, "datasources");
      return;
    case "bucket":
      openPanel("files");
      expandAccordionSection(fileExplorerPanelAtom, "remote-storage");
      return;
    case "cache":
      // No-ops if the cache panel is hidden (not in the layout)
      openPanel("cache");
      return;
    default:
      assertNever(kind);
  }
}
