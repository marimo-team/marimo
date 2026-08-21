/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { keyboardShortcutExtensionsAtom } from "@/core/config/config";
import type { ExtensionHotkeyAction } from "@/core/hotkeys/hotkeys";
import { useHotkey } from "@/hooks/useHotkey";
import { Objects } from "@/utils/objects";

export const KEYBOARD_SHORTCUT_EVENT = "marimo:keyboard-shortcut";

export const KeyboardShortcutExtensions: React.FC = () => {
  const shortcuts = useAtomValue(keyboardShortcutExtensionsAtom);

  return (
    <>
      {Objects.keys(shortcuts).map((action) => (
        <KeyboardShortcutExtension action={action} key={action} />
      ))}
    </>
  );
};

const KeyboardShortcutExtension = ({
  action,
}: {
  action: ExtensionHotkeyAction;
}) => {
  useHotkey(action, () => {
    window.dispatchEvent(
      new CustomEvent(KEYBOARD_SHORTCUT_EVENT, { detail: { action } }),
    );
  });
  return null;
};
