/* Copyright 2023 Marimo. All rights reserved. */
import { HotkeyAction, HOTKEYS } from "@/core/hotkeys/hotkeys";
import { isPlatformMac } from "@/core/shortcuts/shortcuts";
import { Kbd } from "../ui/kbd";

export function renderShortcut(shortcut: HotkeyAction) {
  const hotkey = HOTKEYS.getHotkey(shortcut);

  return (
    <span className="flex">
      {hotkey.name}{" "}
      <span className="flex ml-1 gap-1">
        {prettyPrintHotkey(hotkey.key).map((key) => (
          <Kbd key={key}>{capitalize(key)}</Kbd>
        ))}
      </span>
    </span>
  );
}

export function renderMinimalShortcut(shortcut: HotkeyAction) {
  const hotkey = HOTKEYS.getHotkey(shortcut);

  return (
    <span className="text-xs flex gap-1 text-muted-foreground items-center">
      {prettyPrintHotkey(hotkey.key).map((key) => (
        <span key={key}>{capitalize(key)}</span>
      ))}
    </span>
  );
}

export function prettyPrintHotkey(keyboard: string) {
  return keyboard.split("-").map((key) => {
    switch (key.toLowerCase()) {
      case "cmd":
        return "⌘";
      case "meta":
        return isPlatformMac() ? "⌘" : "ctrl";
      case "shift":
        return "shift";
      case "alt":
        return isPlatformMac() ? "⌥" : "alt";
      case "control":
      case "ctrl":
        return isPlatformMac() ? "⌃" : "ctrl";
      default:
        return key.toLowerCase();
    }
  });
}

function capitalize(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
