/* Copyright 2024 Marimo. All rights reserved. */
import { atomWithReducer } from "jotai/utils";

interface SidebarState {
  isOpen: boolean;
}

interface SidebarAction {
  type: "toggle";
  isOpen: boolean;
}

export const sidebarAtom = atomWithReducer<SidebarState, SidebarAction>(
  { isOpen: true },
  (prev, action) => {
    if (!action) {
      return prev;
    }

    switch (action.type) {
      case "toggle":
        return { ...prev, isOpen: action.isOpen };
      default:
        return prev;
    }
  },
);
