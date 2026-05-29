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
  ServerIcon,
  SquareDashedBottomCodeIcon,
  TerminalSquareIcon,
  TextSearchIcon,
  VariableIcon,
  XCircleIcon,
} from "lucide-react";
import { getFeatureFlag } from "@/core/config/feature-flag";
import type { Capabilities } from "@/core/kernel/messages";
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
  | "cache"
  | "server-logs";

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
  /** Which section this panel belongs to by default */
  defaultSection: PanelSection;
  /** Capability required for this panel to be visible. If the capability is false, the panel is hidden. */
  requiredCapability?: keyof Capabilities;
  /** Additional search keywords for the command palette */
  additionalKeywords?: string[];
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
    additionalKeywords: ["explorer", "browser", "directory"],
  },
  {
    type: "variables",
    Icon: VariableIcon,
    label: "Variables",
    tooltip: "Explore variables and data sources",
    defaultSection: "sidebar",
    additionalKeywords: ["state", "scope", "inspector"],
  },
  {
    type: "packages",
    Icon: BoxIcon,
    label: "Packages",
    tooltip: "Manage packages",
    defaultSection: "sidebar",
    additionalKeywords: ["dependencies", "pip", "install"],
  },
  {
    type: "ai",
    Icon: BotIcon,
    label: "AI",
    tooltip: "Chat & Agents",
    defaultSection: "sidebar",
    additionalKeywords: ["chat", "copilot", "assistant"],
  },
  {
    type: "outline",
    Icon: ScrollTextIcon,
    label: "Outline",
    tooltip: "View outline",
    defaultSection: "sidebar",
    additionalKeywords: ["toc", "structure", "headings"],
  },
  {
    type: "documentation",
    Icon: TextSearchIcon,
    label: "Docs",
    tooltip: "View live docs",
    defaultSection: "sidebar",
    additionalKeywords: ["reference", "api"],
  },
  {
    type: "dependencies",
    Icon: NetworkIcon,
    label: "Dependencies",
    tooltip: "Explore dependencies",
    defaultSection: "sidebar",
    additionalKeywords: ["graph", "imports"],
  },
  // Developer panel defaults
  {
    type: "errors",
    Icon: XCircleIcon,
    label: "Errors",
    tooltip: "View errors",
    defaultSection: "developer-panel",
    additionalKeywords: ["exceptions", "problems", "diagnostics"],
  },
  {
    type: "scratchpad",
    Icon: NotebookPenIcon,
    label: "Scratchpad",
    tooltip: "Scratchpad",
    defaultSection: "developer-panel",
    additionalKeywords: ["scratch", "draft", "playground"],
  },
  {
    type: "tracing",
    Icon: ActivityIcon,
    label: "Tracing",
    tooltip: "View tracing",
    defaultSection: "developer-panel",
    additionalKeywords: ["profiling", "performance"],
  },
  {
    type: "secrets",
    Icon: KeyRoundIcon,
    label: "Secrets",
    tooltip: "Manage secrets",
    defaultSection: "developer-panel",
    hidden: isWasm(),
    additionalKeywords: ["env", "environment", "keys", "credentials"],
  },
  {
    type: "logs",
    Icon: FileTextIcon,
    label: "Logs",
    tooltip: "View logs",
    defaultSection: "developer-panel",
    additionalKeywords: ["console", "stdout"],
  },
  {
    type: "terminal",
    Icon: TerminalSquareIcon,
    label: "Terminal",
    tooltip: "Terminal",
    hidden: isWasm(),
    defaultSection: "developer-panel",
    requiredCapability: "terminal",
    additionalKeywords: ["shell", "console", "bash", "command"],
  },
  {
    type: "snippets",
    Icon: SquareDashedBottomCodeIcon,
    label: "Snippets",
    tooltip: "Snippets",
    defaultSection: "developer-panel",
    additionalKeywords: ["templates", "examples"],
  },
  {
    type: "cache",
    Icon: DatabaseZapIcon,
    label: "Cache",
    tooltip: "View cache",
    defaultSection: "developer-panel",
    hidden: !getFeatureFlag("cache_panel"),
    additionalKeywords: ["memory", "memoize"],
  },
  {
    type: "server-logs",
    Icon: ServerIcon,
    label: "Server Logs",
    tooltip: "View server logs",
    hidden: !import.meta.env.DEV,
    defaultSection: "developer-panel",
  },
];

export const PANEL_MAP = new Map<PanelType, PanelDescriptor>(
  PANELS.map((p) => [p.type, p]),
);

/**
 * Check if a panel should be hidden based on its `hidden` property
 * and `requiredCapability`.
 */
export function isPanelHidden(
  panel: PanelDescriptor,
  capabilities: Capabilities,
): boolean {
  if (panel.hidden) {
    return true;
  }
  if (panel.requiredCapability && !capabilities[panel.requiredCapability]) {
    return true;
  }
  return false;
}
