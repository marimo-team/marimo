/* Copyright 2024 Marimo. All rights reserved. */
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { isPlatformMac } from "@/core/hotkeys/shortcuts";
import { Kbd } from "../ui/kbd";
import { DropdownMenuShortcut } from "../ui/dropdown-menu";
import { Tooltip } from "../ui/tooltip";
import { hotkeysAtom } from "@/core/config/config";
import { useAtomValue } from "jotai";
import { cn } from "@/utils/cn";

export function renderShortcut(shortcut: HotkeyAction) {
  return <Shortcut shortcut={shortcut} />;
}

const Shortcut: React.FC<{ shortcut: HotkeyAction }> = ({ shortcut }) => {
  const hotkeys = useAtomValue(hotkeysAtom);
  const hotkey = hotkeys.getHotkey(shortcut);

  return (
    <span className="flex">
      <span className="mr-2">{hotkey.name}</span>
      <KeyboardHotkeys shortcut={hotkey.key} />
    </span>
  );
};

export const KeyboardHotkeys: React.FC<{
  className?: string;
  shortcut: string;
}> = ({ shortcut, className }) => {
  const keys = shortcut.split("-");

  return (
    <div className={cn("flex gap-1", className)}>
      {keys.map(prettyPrintHotkey).map(([label, symbol]) => {
        if (symbol) {
          return (
            <Tooltip
              asChild={false}
              tabIndex={-1}
              key={label}
              content={label}
              delayDuration={300}
            >
              <Kbd key={label}>{symbol}</Kbd>
            </Tooltip>
          );
        }
        return <Kbd key={label}>{capitalize(label)}</Kbd>;
      })}
    </div>
  );
};

export function renderMinimalShortcut(shortcut: HotkeyAction) {
  return <MinimalShortcut shortcut={shortcut} />;
}

export const MinimalShortcut: React.FC<{
  className?: string;
  shortcut: HotkeyAction;
}> = ({ className, shortcut }) => {
  const hotkeys = useAtomValue(hotkeysAtom);
  const hotkey = hotkeys.getHotkey(shortcut);

  return <MinimalHotkeys shortcut={hotkey.key} className={className} />;
};

export const MinimalHotkeys: React.FC<{
  className?: string;
  shortcut: string;
}> = ({ shortcut, className }) => {
  const keys = shortcut.split("-");
  return (
    <DropdownMenuShortcut className={cn("flex gap-1 items-center", className)}>
      {keys.map(prettyPrintHotkey).map(([label, symbol]) => {
        if (symbol) {
          return (
            <Tooltip
              key={label}
              content={label}
              delayDuration={300}
              tabIndex={-1}
            >
              <span key={label}>{symbol}</span>
            </Tooltip>
          );
        }
        return <span key={label}>{capitalize(label)}</span>;
      })}
    </DropdownMenuShortcut>
  );
};

function prettyPrintHotkey(key: string): [label: string, symbol?: string] {
  const platform = isPlatformMac() ? "mac" : "default";

  const lowerKey = key.toLowerCase();
  const keyData = KEY_MAPPINGS[key.toLowerCase()];
  if (keyData) {
    const symbol = keyData.symbols[platform] || keyData.symbols.default;
    return [keyData.label, symbol];
  }

  return [lowerKey];
}

interface KeyData {
  symbols: {
    mac?: string;
    windows?: string;
    default: string;
  };
  label: string;
}

const KEY_MAPPINGS: Record<string, KeyData> = {
  ctrl: {
    symbols: { mac: "⌃", default: "Ctrl" },
    label: "Control",
  },
  control: {
    symbols: { mac: "⌃", default: "Ctrl" },
    label: "Control",
  },
  shift: {
    symbols: { mac: "⇧", default: "Shift" },
    label: "Shift",
  },
  alt: {
    symbols: { mac: "⌥", default: "Alt" },
    label: "Alt/Option",
  },
  escape: {
    symbols: { mac: "⎋", default: "Esc" },
    label: "Escape",
  },
  arrowup: {
    symbols: { default: "↑" },
    label: "Arrow Up",
  },
  arrowdown: {
    symbols: { default: "↓" },
    label: "Arrow Down",
  },
  arrowleft: {
    symbols: { default: "←" },
    label: "Arrow Left",
  },
  arrowright: {
    symbols: { default: "→" },
    label: "Arrow Right",
  },
  backspace: {
    symbols: { mac: "⌫", default: "⟵" },
    label: "Backspace",
  },
  tab: {
    symbols: { mac: "⇥", default: "⭾" },
    label: "Tab",
  },
  capslock: {
    symbols: { default: "⇪" },
    label: "Caps Lock",
  },
  fn: {
    symbols: { default: "Fn" },
    label: "Fn",
  },
  cmd: {
    symbols: { mac: "⌘", windows: "⊞ Win", default: "Command" },
    label: "Command",
  },
  insert: {
    symbols: { default: "Ins" },
    label: "Insert",
  },
  delete: {
    symbols: { mac: "⌦", default: "Del" },
    label: "Delete",
  },
  home: {
    symbols: { mac: "↖", default: "Home" },
    label: "Home",
  },
  end: {
    symbols: { mac: "↘", default: "End" },
    label: "End",
  },
};

function capitalize(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
