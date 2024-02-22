/* Copyright 2024 Marimo. All rights reserved. */
import { HotkeyAction } from "@/core/hotkeys/hotkeys";

/**
 * Shared interface to render a user action in the editor.
 * This can be in a dropdown menu, context menu, or toolbar.
 */
export interface ActionButton {
  label: string;
  variant?: "danger";
  disableClick?: boolean;
  icon?: React.ReactNode;
  hidden?: boolean;
  rightElement?: React.ReactNode;
  hotkey?: HotkeyAction;
  handle: (event?: Event) => void;
  divider?: boolean;
  dropdown?: ActionButton[];
}

export function isParentAction(
  action: ActionButton,
): action is ActionButton & { dropdown: ActionButton[] } {
  return action.dropdown !== undefined;
}

/**
 * Flattens all actions into a single array.
 * Any parent actions will be removed, but their labels will be prepended to the child actions.
 */
export function flattenActions(
  actions: ActionButton[],
  prevLabel = "",
): ActionButton[] {
  return actions.flatMap((action) => {
    if (isParentAction(action)) {
      return flattenActions(action.dropdown, `${prevLabel + action.label} > `);
    }
    return { ...action, label: prevLabel + action.label };
  });
}
