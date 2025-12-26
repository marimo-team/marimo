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
  TerminalSquareIcon,
  TextSearchIcon,
  XCircleIcon,
} from "lucide-react";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { isWasm } from "@/core/wasm/utils";

export type PanelType =
  | "files"
  | "variables"
  | "outline"
  | "dependencies"
  | "packages"
  | "documentation"
  | "snippets"
  | "datasources"
  | "ai"
  | "cache";

export interface PanelDescriptor {
  id: PanelType;
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
    id: "files",
    Icon: FolderTreeIcon,
    tooltip: "View files",
    position: "sidebar",
  },
  // Because notebooks uniquely have data in RAM,
  // it's important to give humans visibility into
  // what that data is.
  {
    id: "variables",
    Icon: FunctionSquareIcon,
    tooltip: "Explore variables",
    position: "sidebar",
  },
  {
    id: "datasources",
    Icon: DatabaseIcon,
    tooltip: "Explore data sources",
    position: "sidebar",
  },
  // Every notebook has a package environment that must
  // be managed.
  {
    id: "packages",
    Icon: BoxIcon,
    tooltip: "Manage packages",
    position: "sidebar",
  },
  // 2. "AI" panel.
  //
  // The AI panel holds both agents and in-editor chat.
  {
    id: "ai",
    Icon: BotIcon,
    tooltip: "Chat & Agents",
    position: "sidebar",
  },
  {
    // TODO(akshayka): Consider making snippets default
    // off, user configuration to enable.
    id: "snippets",
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
    id: "outline",
    Icon: ScrollTextIcon,
    tooltip: "View outline",
    position: "sidebar",
  },
  {
    id: "documentation",
    Icon: TextSearchIcon,
    tooltip: "View live docs",
    position: "sidebar",
  },
  {
    // TODO(akshayka): Consider making dependencies
    // default off; the minimap is a more effective
    // overview.
    id: "dependencies",
    Icon: NetworkIcon,
    tooltip: "Explore dependencies",
    position: "sidebar",
  },
];

export const PANEL_MAP = new Map<PanelType, PanelDescriptor>(
  PANELS.map((p) => [p.id, p]),
);

export type DeveloperPanelTabType =
  | "errors"
  | "scratchpad"
  | "tracing"
  | "secrets"
  | "logs"
  | "terminal"
  | "cache";

export interface DeveloperPanelTabDescriptor {
  type: DeveloperPanelTabType;
  Icon: LucideIcon;
  label: string;
  hidden?: boolean;
}

export const DEVELOPER_PANEL_TABS: DeveloperPanelTabDescriptor[] = [
  {
    type: "errors",
    Icon: XCircleIcon,
    label: "Errors",
  },
  {
    type: "scratchpad",
    Icon: NotebookPenIcon,
    label: "Scratchpad",
  },
  {
    type: "tracing",
    Icon: ActivityIcon,
    label: "Tracing",
  },
  {
    type: "secrets",
    Icon: KeyRoundIcon,
    label: "Secrets",
    hidden: isWasm(),
  },
  {
    type: "logs",
    Icon: FileTextIcon,
    label: "Logs",
  },
  {
    type: "terminal",
    Icon: TerminalSquareIcon,
    label: "Terminal",
  },
  // TODO(akshayka): The cache panel should not be default shown,
  // even when it's out of feature flag. (User config to turn it on.)
  {
    type: "cache",
    Icon: DatabaseZapIcon,
    label: "Cache",
    hidden: !getFeatureFlag("cache_panel"),
  },
];
