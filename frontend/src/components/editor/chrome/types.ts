/* Copyright 2024 Marimo. All rights reserved. */

import {
  ActivityIcon,
  BotIcon,
  BoxIcon,
  DatabaseIcon,
  DatabaseZapIcon,
  FileTextIcon,
  FolderTreeIcon,
  FunctionSquareIcon,
  KeyRoundIcon,
  type LucideIcon,
  NetworkIcon,
  NotebookPenIcon,
  ScrollTextIcon,
  SquareDashedBottomCodeIcon,
  TextSearchIcon,
} from "lucide-react";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { isWasm } from "@/core/wasm/utils";

export type PanelType =
  | "files"
  | "variables"
  | "outline"
  | "dependencies"
  | "tracing"
  | "packages"
  | "documentation"
  | "snippets"
  | "datasources"
  | "scratchpad"
  | "ai"
  | "cache"
  | "secrets"
  | "logs";

export interface PanelDescriptor {
  type: PanelType;
  Icon: LucideIcon;
  hidden?: boolean;
  tooltip: string;
  position: "sidebar" | "footer";
}

/* Panels are ordered in roughly decreasing order of importance as well as
 * logically grouped.
 *
 * 1. Must-have panels first.
 * 2. Panels that can add cells to the editor.
 * 3. Nice-to-have observability panels.
 */
export const PANELS: PanelDescriptor[] = [
  // 1. Must-have panels.
  //
  // The files panel is at the top to orient
  // users within their filesystem and give
  // them a quick glance at their project structure,
  // without having to leave their editor.
  {
    type: "files",
    Icon: FolderTreeIcon,
    tooltip: "View files",
    position: "sidebar",
  },
  // Because notebooks uniquely have data in RAM,
  // it's important to give humans visibility into
  // what that data is.
  {
    type: "variables",
    Icon: FunctionSquareIcon,
    tooltip: "Explore variables",
    position: "sidebar",
  },
  {
    type: "datasources",
    Icon: DatabaseIcon,
    tooltip: "Explore data sources",
    position: "sidebar",
  },
  // Every notebook has a package environment that must
  // be managed.
  {
    type: "packages",
    Icon: BoxIcon,
    tooltip: "Manage packages",
    position: "sidebar",
  },
  // 2. "AI" panel.
  //
  // The AI panel holds both agents and in-editor chat.
  {
    type: "ai",
    Icon: BotIcon,
    tooltip: "Chat & Agents",
    position: "sidebar",
  },
  // Scratchpad is the only way users can
  // code without DAG restrictions, so it is
  // privileged.
  {
    type: "scratchpad",
    Icon: NotebookPenIcon,
    tooltip: "Scratchpad",
    position: "sidebar",
  },
  {
    // TODO(akshayka): Consider making snippets default
    // off, user configuration to enable.
    type: "snippets",
    Icon: SquareDashedBottomCodeIcon,
    tooltip: "Snippets",
    position: "sidebar",
  },
  // 3. Nice-to-have observability panels.
  //
  // Utility panels that provide observability
  // into the state or structure of the notebook. These
  // observability panels are less crucial than variables
  // or datasets, so they are positioned at the end of the
  // sidebar.
  {
    type: "outline",
    Icon: ScrollTextIcon,
    tooltip: "View outline",
    position: "sidebar",
  },
  {
    type: "documentation",
    Icon: TextSearchIcon,
    tooltip: "View live docs",
    position: "sidebar",
  },
  {
    type: "logs",
    Icon: FileTextIcon,
    tooltip: "Notebook logs",
    position: "sidebar",
  },
  {
    // TODO(akshayka): Consider making dependencies
    // default off; the minimap is a more effective
    // overview.
    type: "dependencies",
    Icon: NetworkIcon,
    tooltip: "Explore dependencies",
    position: "sidebar",
  },
  {
    type: "tracing",
    Icon: ActivityIcon,
    tooltip: "Tracing",
    position: "sidebar",
  },
  {
    // Not supported in WebAssembly yet
    type: "secrets",
    Icon: KeyRoundIcon,
    tooltip: "Secrets",
    hidden: isWasm(),
    position: "sidebar",
  },
  // TODO(akshayka): The cache panel should not be default shown,
  // even when it's out of feature flag. (User config to
  // turn it on.)
  {
    type: "cache",
    Icon: DatabaseZapIcon,
    tooltip: "Manage cache",
    position: "sidebar",
    hidden: !getFeatureFlag("cache_panel"),
  },
  ];
