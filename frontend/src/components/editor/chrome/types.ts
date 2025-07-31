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
}

export const PANELS: PanelDescriptor[] = [
  {
    type: "files",
    Icon: FolderTreeIcon,
    tooltip: "View files",
    position: "sidebar",
  },
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
  {
    type: "dependencies",
    Icon: NetworkIcon,
    tooltip: "Explore dependencies",
    position: "sidebar",
  },
  {
    type: "packages",
    Icon: BoxIcon,
    tooltip: "Manage packages",
    position: "sidebar",
  },
  {
    type: "outline",
    Icon: ScrollTextIcon,
    tooltip: "View outline",
    position: "sidebar",
  },
  {
    type: "chat",
    Icon: BotMessageSquareIcon,
    tooltip: "Chat with AI",
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
    type: "tracing",
    Icon: ActivityIcon,
    tooltip: "Tracing",
    position: "sidebar",
  },
  {
    type: "snippets",
    Icon: SquareDashedBottomCodeIcon,
    tooltip: "Snippets",
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
  {
    type: "scratchpad",
    Icon: NotebookPenIcon,
    tooltip: "Scratchpad",
    position: "sidebar",
  },
  {
    type: "errors",
    Icon: XCircleIcon,
    tooltip: "View errors",
    position: "footer",
  },
];
