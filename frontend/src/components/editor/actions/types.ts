/* Copyright 2024 Marimo. All rights reserved. */
import { HotkeyAction } from "@/core/hotkeys/hotkeys";

/**
 * Shared interface to render a user action in the editor.
 * This can be in a dropdown menu, context menu, or toolbar.
 */
export interface ActionButton {
  label: string;
  variant?: "danger";
  hotkey?: HotkeyAction;
  disableClick?: boolean;
  icon?: React.ReactNode;
  hidden?: boolean;
  rightElement?: React.ReactNode;
  handle: (event?: Event) => void;
}
