/* Copyright 2026 Marimo. All rights reserved. */
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";

/**
 * Shared interface to render a user action in the editor.
 * This can be in a dropdown menu, context menu, toolbar, or command palette.
 */
export interface ActionButton {
  label: string;
  labelElement?: React.ReactNode;
  description?: string;
  disabled?: boolean;
  tooltip?: React.ReactNode;
  variant?: "danger" | "muted" | "disabled";
  disableClick?: boolean;
  icon?: React.ReactElement;
  // whether the action is applicable
  hidden?: boolean;
  // whether to show the action in a menu
  redundant?: boolean;
  rightElement?: React.ReactNode;
  hotkey?: HotkeyAction;
  handle: (event?: Event) => void;
  /**
   * Special handler for headless contexts: e.g. a command palette.
   */
  handleHeadless?: (event?: Event) => void;
  divider?: boolean;
  dropdown?: ActionButton[];
  additionalKeywords?: string[];
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
  inheritedKeywords: string[] = [],
): ActionButton[] {
  return actions.flatMap((action) => {
    if (!action.label || action.hidden) {
      return [];
    }
    const additionalKeywords = [
      ...inheritedKeywords,
      ...(action.additionalKeywords ?? []),
    ];
    if (isParentAction(action)) {
      return flattenActions(
        action.dropdown,
        `${prevLabel + action.label} > `,
        additionalKeywords,
      );
    }
    return {
      ...action,
      label: prevLabel + action.label,
      additionalKeywords:
        additionalKeywords.length > 0
          ? [...new Set(additionalKeywords)]
          : undefined,
    };
  });
}
