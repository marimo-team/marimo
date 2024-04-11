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
} from "lucide-react";

export type PanelType =
  | "files"
  | "errors"
  | "variables"
  | "outline"
  | "dependencies"
  | "documentation"
  | "snippets"
  | "logs";

export const PANEL_ICONS: Record<PanelType, LucideIcon> = {
  errors: XCircleIcon,
  files: FolderTreeIcon,
  variables: FunctionSquareIcon,
  dependencies: NetworkIcon,
  outline: ScrollTextIcon,
  documentation: TextSearchIcon,
  logs: FileTextIcon,
  snippets: SquareDashedBottomCodeIcon,
};

export const PANEL_TYPES: PanelType[] = Objects.keys(PANEL_ICONS);
