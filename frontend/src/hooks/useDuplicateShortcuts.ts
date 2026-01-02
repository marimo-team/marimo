/* Copyright 2026 Marimo. All rights reserved. */

import { useMemo } from "react";
import type {
  HotkeyAction,
  HotkeyGroup,
  HotkeyProvider,
} from "@/core/hotkeys/hotkeys";

export interface DuplicateGroup {
  key: string;
  actions: { action: HotkeyAction; name: string }[];
}

export interface DuplicateShortcutsResult {
  /** All groups of duplicate shortcuts */
  duplicates: DuplicateGroup[];
  /** Check if a specific action has duplicate shortcuts */
  hasDuplicate: (action: HotkeyAction) => boolean;
  /** Get all actions that share the same shortcut as the given action */
  getDuplicatesFor: (action: HotkeyAction) => HotkeyAction[];
}

/**
 * Normalizes a keyboard shortcut key for comparison.
 * - Converts to lowercase
 * - Replaces + with - for consistent comparison
 * - Trims whitespace
 */
export function normalizeShortcutKey(key: string): string {
  return key.toLowerCase().replaceAll("+", "-").trim();
}

/**
 * Detects duplicate keyboard shortcuts in a hotkey provider.
 * Returns information about which shortcuts are duplicated and provides utilities
 * to check if specific actions have duplicates.
 *
 * This is a pure function that can be tested independently of React.
 *
 * @param hotkeys - The hotkey provider to check for duplicates
 * @param ignoreGroup - Optional group to exclude from duplicate detection (e.g., "Markdown")
 */
export function findDuplicateShortcuts(
  hotkeys: HotkeyProvider,
  ignoreGroup?: HotkeyGroup,
): DuplicateShortcutsResult {
  // Get all groups to check for ignored actions
  const groups = hotkeys.getHotkeyGroups();
  const ignoredActions = ignoreGroup
    ? new Set(groups[ignoreGroup] || [])
    : new Set();

  // Group actions by their key binding
  const keyMap = new Map<string, { action: HotkeyAction; name: string }[]>();

  for (const action of hotkeys.iterate()) {
    // Skip actions in ignored groups
    if (ignoredActions.has(action)) {
      continue;
    }

    const hotkey = hotkeys.getHotkey(action);

    // Skip empty keys (not set)
    if (!hotkey.key || hotkey.key.trim() === "") {
      continue;
    }

    const normalizedKey = normalizeShortcutKey(hotkey.key);

    if (!keyMap.has(normalizedKey)) {
      keyMap.set(normalizedKey, []);
    }

    const existing = keyMap.get(normalizedKey);
    if (existing) {
      existing.push({
        action,
        name: hotkey.name,
      });
    }
  }

  // Filter to only groups with duplicates (more than one action per key)
  const duplicates: DuplicateGroup[] = [];
  const duplicateActionSet = new Set<HotkeyAction>();

  for (const [key, actions] of keyMap.entries()) {
    if (actions.length > 1) {
      duplicates.push({ key, actions });
      for (const { action } of actions) {
        duplicateActionSet.add(action);
      }
    }
  }

  // Helper to check if an action has duplicates
  const hasDuplicate = (action: HotkeyAction): boolean => {
    return duplicateActionSet.has(action);
  };

  // Helper to get all duplicates for a specific action
  const getDuplicatesFor = (action: HotkeyAction): HotkeyAction[] => {
    const hotkey = hotkeys.getHotkey(action);
    if (!hotkey.key || hotkey.key.trim() === "") {
      return [];
    }

    const normalizedKey = normalizeShortcutKey(hotkey.key);

    const group = duplicates.find((d) => d.key === normalizedKey);
    if (!group || group.actions.length <= 1) {
      return [];
    }

    return group.actions
      .filter((a) => a.action !== action)
      .map((a) => a.action);
  };

  return {
    duplicates,
    hasDuplicate,
    getDuplicatesFor,
  };
}

/**
 * Hook to detect duplicate keyboard shortcuts.
 * Returns information about which shortcuts are duplicated and provides utilities
 * to check if specific actions have duplicates.
 *
 * @param hotkeys - The hotkey provider to check for duplicates
 * @param ignoreGroup - Optional group to exclude from duplicate detection (e.g., "Markdown")
 */
export function useDuplicateShortcuts(
  hotkeys: HotkeyProvider,
  ignoreGroup?: HotkeyGroup,
): DuplicateShortcutsResult {
  return useMemo(
    () => findDuplicateShortcuts(hotkeys, ignoreGroup),
    [hotkeys, ignoreGroup],
  );
}
