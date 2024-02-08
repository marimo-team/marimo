/* Copyright 2024 Marimo. All rights reserved. */
import { PrimitiveType } from "compassql/build/src/schema";
import {
  ToggleLeftIcon,
  CalendarIcon,
  HashIcon,
  TypeIcon,
  ListOrderedIcon,
} from "lucide-react";

/**
 * Icon mapping from PrimitiveType to Lucid icon
 */
export const PRIMITIVE_TYPE_ICON: Record<PrimitiveType, React.ReactNode> = {
  [PrimitiveType.BOOLEAN]: (
    <ToggleLeftIcon className="h-5 w-5 inline-flex opacity-60" />
  ),
  [PrimitiveType.DATETIME]: (
    <CalendarIcon className="h-5 w-5 inline-flex opacity-60" />
  ),
  [PrimitiveType.NUMBER]: (
    <HashIcon className="h-5 w-5 inline-flex opacity-60" />
  ),
  [PrimitiveType.STRING]: (
    <TypeIcon className="h-5 w-5 inline-flex opacity-60" />
  ),
  [PrimitiveType.INTEGER]: (
    <ListOrderedIcon className="h-5 w-5 inline-flex opacity-60" />
  ),
};
