/* Copyright 2024 Marimo. All rights reserved. */
import { Objects } from "@/utils/objects";
import {
  XCircleIcon,
  FolderTreeIcon,
  FunctionSquareIcon,
  NetworkIcon,
  ScrollTextIcon,
  TextSearchIcon,
  FileTextIcon,
  LucideIcon,
  SquareDashedBottomCodeIcon,
  SquarePenIcon,
} from "lucide-react";

export type PanelType =
  | "files"
  | "errors"
  | "variables"
  | "outline"
  | "dependencies"
  | "documentation"
  | "snippets"
  | "logs"
  | "scratchpad";

export const PANEL_ICONS: Record<PanelType, LucideIcon> = {
  errors: XCircleIcon,
  files: FolderTreeIcon,
  variables: FunctionSquareIcon,
  dependencies: NetworkIcon,
  outline: ScrollTextIcon,
  documentation: TextSearchIcon,
  logs: FileTextIcon,
  snippets: SquareDashedBottomCodeIcon,
  scratchpad: SquarePenIcon,
};

export const PANEL_TYPES: PanelType[] = Objects.keys(PANEL_ICONS);
