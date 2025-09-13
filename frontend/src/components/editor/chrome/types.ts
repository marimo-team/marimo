/* Copyright 2024 Marimo. All rights reserved. */

import {
  ActivityIcon,
  BotMessageSquareIcon,
  BoxIcon,
  DatabaseIcon,
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
  XCircleIcon,
} from "lucide-react";
import { isWasm } from "@/core/wasm/utils";

export type PanelType =
  | "files"
  | "errors"
  | "variables"
  | "outline"
  | "dependencies"
  | "tracing"
  | "packages"
  | "documentation"
  | "snippets"
  | "datasources"
  | "scratchpad"
  | "chat"
  | "secrets"
  | "logs";

export interface PanelDescriptor {
  type: PanelType;
  Icon: LucideIcon;
  hidden?: boolean;
  tooltip: string;
  position: "sidebar" | "footer";
  extraDescription?: string[];
}

export const PANELS: PanelDescriptor[] = [
  {
    type: "files",
    Icon: FolderTreeIcon,
    tooltip: "View files",
    position: "sidebar",
    extraDescription: ["View files"],
  },
  {
    type: "variables",
    Icon: FunctionSquareIcon,
    tooltip: "Explore variables",
    position: "sidebar",
    extraDescription: ["Explore variables"],
  },
  {
    type: "datasources",
    Icon: DatabaseIcon,
    tooltip: "Explore data sources",
    position: "sidebar",
    extraDescription: ["Explore data sources", "data sources"],
  },
  {
    type: "dependencies",
    Icon: NetworkIcon,
    tooltip: "Explore dependencies",
    position: "sidebar",
    extraDescription: ["Explore dependencies"],
  },
  {
    type: "packages",
    Icon: BoxIcon,
    tooltip: "Manage packages",
    position: "sidebar",
    extraDescription: ["Manage packages", "requirements"],
  },
  {
    type: "outline",
    Icon: ScrollTextIcon,
    tooltip: "View outline",
    position: "sidebar",
    extraDescription: ["View outline", "Show chapter headings"],
  },
  {
    type: "chat",
    Icon: BotMessageSquareIcon,
    tooltip: "Chat with AI",
    position: "sidebar",
    extraDescription: ["Chat with AI", "AI chat"],
  },
  {
    type: "documentation",
    Icon: TextSearchIcon,
    tooltip: "View live docs",
    position: "sidebar",
    extraDescription: ["View live docs", "Show contextual help", "Signature"],
  },
  {
    type: "logs",
    Icon: FileTextIcon,
    tooltip: "Notebook logs",
    position: "sidebar",
    extraDescription: ["Notebook logs"],
  },
  {
    type: "tracing",
    Icon: ActivityIcon,
    tooltip: "Tracing",
    position: "sidebar",
    extraDescription: ["Traces"],
  },
  {
    type: "snippets",
    Icon: SquareDashedBottomCodeIcon,
    tooltip: "Snippets",
    position: "sidebar",
    extraDescription: ["Code snippets"],
  },
  {
    // Not supported in WebAssembly yet
    type: "secrets",
    Icon: KeyRoundIcon,
    tooltip: "Secrets",
    hidden: isWasm(),
    position: "sidebar",
    extraDescription: ["Environment variables"],
  },
  {
    type: "scratchpad",
    Icon: NotebookPenIcon,
    tooltip: "Scratchpad",
    position: "sidebar",
    extraDescription: ["Notes"],
  },
  {
    type: "errors",
    Icon: XCircleIcon,
    tooltip: "View errors",
    position: "footer",
    extraDescription: ["View errors"],
  },
];
