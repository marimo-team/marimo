/* Copyright 2024 Marimo. All rights reserved. */
import { atomWithReducer } from "jotai/utils";

interface SidebarState {
  isOpen: boolean;
  width?: string;
}

interface SidebarAction {
  type: "toggle" | "setWidth";
  isOpen?: boolean;
  width?: string;
}

// Convert numeric values to px units
export const normalizeWidth = (width: string | undefined): string => {
  if (!width) {
    return "288px"; // 72 * 4 (tailwind default)
  }
  // If it's just a number, assume px
  if (/^\d+$/.test(width)) {
    return `${width}px`;
  }
  return width;
};

export const sidebarAtom = atomWithReducer<SidebarState, SidebarAction>(
  { isOpen: true },
  (prev, action) => {
    if (!action) {
      return prev;
    }

    switch (action.type) {
      case "toggle":
        return { ...prev, isOpen: action.isOpen! };
      case "setWidth":
        return { ...prev, width: action.width };
      default:
        return prev;
    }
  },
);
