/* Copyright 2026 Marimo. All rights reserved. */

import {
  ActivityIcon,
  BotIcon,
  BoxIcon,
  DatabaseZapIcon,
  FileTextIcon,
  FolderTreeIcon,
  KeyRoundIcon,
  type LucideIcon,
  NetworkIcon,
  NotebookPenIcon,
  ScrollTextIcon,
  SquareDashedBottomCodeIcon,
  TerminalSquareIcon,
  TextSearchIcon,
  VariableIcon,
  XCircleIcon,
} from "lucide-react";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { isWasm } from "@/core/wasm/utils";

/**
 * Unified panel ID for all panels in sidebar and developer panel
 */
export type PanelType =
  // Sidebar defaults
  | "files"
  | "variables"
  | "outline"
  | "dependencies"
  | "packages"
  | "documentation"
  | "snippets"
  | "ai"
  // Developer panel defaults
  | "errors"
  | "scratchpad"
  | "tracing"
  | "secrets"
  | "logs"
  | "terminal"
  | "cache";

export type PanelSection = "sidebar" | "developer-panel";

export interface PanelDescriptor {
  type: PanelType;
  Icon: LucideIcon;
  /** Short label for developer panel tabs */
  label: string;
  /** Descriptive tooltip for sidebar icons */
  tooltip: string;
  /** If true, the panel is completely unavailable */
  hidden?: boolean;
  /** If true, the panel is available but not shown by default */
  defaultHidden?: boolean;
  /** Which section this panel belongs to by default */
  defaultSection: PanelSection;
}

/**
 * All panels in the application.
 * Panels can be in either sidebar or developer panel, configurable by user.
 */
export const PANELS: PanelDescriptor[] = [
  // Sidebar defaults
  {
    type: "files",
    Icon: FolderTreeIcon,
    label: "Files",
    tooltip: "View files",
    defaultSection: "sidebar",
  },
  {
    type: "variables",
    Icon: VariableIcon,
    label: "Variables",
    tooltip: "Explore variables and data sources",
    defaultSection: "sidebar",
  },
  {
    type: "packages",
    Icon: BoxIcon,
    label: "Packages",
    tooltip: "Manage packages",
    defaultSection: "sidebar",
  },
  {
    type: "ai",
    Icon: BotIcon,
    label: "AI",
    tooltip: "Chat & Agents",
    defaultSection: "sidebar",
  },
  {
    type: "snippets",
    Icon: SquareDashedBottomCodeIcon,
    label: "Snippets",
    tooltip: "Snippets",
    defaultSection: "sidebar",
    defaultHidden: true,
  },
  {
    type: "outline",
    Icon: ScrollTextIcon,
    label: "Outline",
    tooltip: "View outline",
    defaultSection: "sidebar",
  },
  {
    type: "documentation",
    Icon: TextSearchIcon,
    label: "Docs",
    tooltip: "View live docs",
    defaultSection: "sidebar",
  },
  {
    type: "dependencies",
    Icon: NetworkIcon,
    label: "Dependencies",
    tooltip: "Explore dependencies",
    defaultSection: "sidebar",
  },
  // Developer panel defaults
  {
    type: "errors",
    Icon: XCircleIcon,
    label: "Errors",
    tooltip: "View errors",
    defaultSection: "developer-panel",
  },
  {
    type: "scratchpad",
    Icon: NotebookPenIcon,
    label: "Scratchpad",
    tooltip: "Scratchpad",
    defaultSection: "developer-panel",
  },
  {
    type: "tracing",
    Icon: ActivityIcon,
    label: "Tracing",
    tooltip: "View tracing",
    defaultSection: "developer-panel",
  },
  {
    type: "secrets",
    Icon: KeyRoundIcon,
    label: "Secrets",
    tooltip: "Manage secrets",
    defaultSection: "developer-panel",
    hidden: isWasm(),
  },
  {
    type: "logs",
    Icon: FileTextIcon,
    label: "Logs",
    tooltip: "View logs",
    defaultSection: "developer-panel",
  },
  {
    type: "terminal",
    Icon: TerminalSquareIcon,
    label: "Terminal",
    tooltip: "Terminal",
    defaultSection: "developer-panel",
  },
  {
    type: "cache",
    Icon: DatabaseZapIcon,
    label: "Cache",
    tooltip: "View cache",
    defaultSection: "developer-panel",
    hidden: !getFeatureFlag("cache_panel"),
  },
];

export const PANEL_MAP = new Map<PanelType, PanelDescriptor>(
  PANELS.map((p) => [p.type, p]),
);
