/* Copyright 2024 Marimo. All rights reserved. */
import { useHotkey } from "../../../hooks/useHotkey";
import {
  Dialog,
  DialogContent,
  DialogPortal,
  DialogOverlay,
  DialogHeader,
  DialogTitle,
} from "../../ui/dialog";
import { KeyboardHotkeys } from "../../shortcuts/renderShortcut";
import {
  type HotkeyAction,
  type HotkeyGroup,
  getDefaultHotkey,
} from "@/core/hotkeys/hotkeys";
import { atom, useAtom, useAtomValue } from "jotai";
import { useState } from "react";
import { EditIcon, XIcon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { hotkeysAtom, useResolvedMarimoConfig } from "@/core/config/config";
import { saveUserConfig } from "@/core/network/requests";
import { isPlatformMac } from "@/core/hotkeys/shortcuts";
import { Button } from "@/components/ui/button";
import type { UserConfig } from "@/core/config/config-schema";

export const keyboardShortcutsAtom = atom(false);

export const KeyboardShortcuts: React.FC = () => {
  const [isOpen, setIsOpen] = useAtom(keyboardShortcutsAtom);
  const [editingShortcut, setEditingShortcut] = useState<HotkeyAction | null>(
    null,
  );
  const [newShortcut, setNewShortcut] = useState<string[]>([]);
  const [config, setConfig] = useResolvedMarimoConfig();
  const hotkeys = useAtomValue(hotkeysAtom);

  useHotkey("global.showHelp", () => setIsOpen((v) => !v));

  const saveConfigOptimistic = async (newConfig: UserConfig) => {
    const prevConfig = { ...config };
    setConfig(newConfig);
    await saveUserConfig({ config: newConfig }).catch((error) => {
      setConfig(prevConfig);
      throw error;
    });
  };

  const handleNewShortcut = async (shortcut: string[]) => {
    if (!editingShortcut) {
      return;
    }

    const shortcutString = shortcut.join("-");
    const newConfig = {
      ...config,
      keymap: {
        ...config.keymap,
        overrides: {
          ...config.keymap.overrides,
          [editingShortcut]: shortcutString,
        },
      },
    };

    setEditingShortcut(null);
    setNewShortcut([]);
    await saveConfigOptimistic(newConfig);
  };

  const handleResetShortcut = async () => {
    if (!editingShortcut) {
      return;
    }

    const newConfig = {
      ...config,
      keymap: {
        ...config.keymap,
        overrides: {
          ...config.keymap.overrides,
        },
      },
    };

    // Delete the shortcut from the overrides
    const { [editingShortcut]: _unused, ...rest } = newConfig.keymap.overrides;
    newConfig.keymap.overrides = rest;

    setEditingShortcut(null);
    setNewShortcut([]);
    await saveConfigOptimistic(newConfig);
  };

  const handleResetAllShortcuts = async () => {
    if (
      !window.confirm(
        "Are you sure you want to reset all shortcuts to their default values?",
      )
    ) {
      return;
    }

    const newConfig = {
      ...config,
      keymap: {
        ...config.keymap,
        overrides: {},
      },
    };

    setEditingShortcut(null);
    setNewShortcut([]);
    await saveConfigOptimistic(newConfig);
  };

  if (!isOpen) {
    return null;
  }

  const renderItem = (action: HotkeyAction) => {
    const hotkey = hotkeys.getHotkey(action);

    if (editingShortcut === action) {
      const defaultHotkey = getDefaultHotkey(action);
      return (
        <div key={action}>
          <Input
            defaultValue={newShortcut.join("+")}
            placeholder={hotkey.name}
            onKeyDown={(e) => {
              e.preventDefault();
              const next: string[] = [];

              // Skip if the key is a modifier key
              if (
                e.key === "Meta" ||
                e.key === "Control" ||
                e.key === "Alt" ||
                e.key === "Shift"
              ) {
                return;
              }

              if (e.metaKey) {
                next.push(isPlatformMac() ? "Cmd" : "Meta");
              }
              if (e.ctrlKey) {
                next.push("Ctrl");
              }
              if (e.altKey) {
                next.push("Alt");
              }
              if (e.shiftKey) {
                next.push("Shift");
              }

              // We don't allow `-` to be a shortcut key, since it's used to
              // separate keys in the shortcut string
              if (e.key === "-") {
                return;
              }
              // If escape is pressed, without any modifier keys, cancel editing
              // We don't allow escape to be a shortcut key along, since it's used to
              // remove focus from many elements
              if (e.key === "Escape" && next.length === 0) {
                setEditingShortcut(null);
                setNewShortcut([]);
                return;
              }

              let key = e.key.toLowerCase();
              // Handle edge cases
              if (e.key === " ") {
                key = "Space";
              }

              next.push(key);

              handleNewShortcut(next);
            }}
            autoFocus={true}
            endAdornment={
              <Button
                variant="text"
                size="xs"
                className="mb-0"
                onClick={() => {
                  setEditingShortcut(null);
                  setNewShortcut([]);
                }}
              >
                <XIcon className="w-4 h-4" />
              </Button>
            }
          />
          <div className="flex items-center justify-between w-full">
            <span className="text-muted-foreground text-xs">
              Press a key combination
            </span>
            {defaultHotkey.key !== hotkey.key && (
              <span
                className="text-xs cursor-pointer text-primary"
                onClick={handleResetShortcut}
              >
                Reset to default:{" "}
                <span className="font-mono">{defaultHotkey.key}</span>
              </span>
            )}
          </div>
        </div>
      );
    }

    return (
      <div
        key={action}
        className="grid grid-cols-[auto,2fr,3fr] gap-2 items-center"
      >
        {hotkeys.isEditable(action) ? (
          <EditIcon
            className="cursor-pointer opacity-60 hover:opacity-100 text-muted-foreground w-3 h-3"
            onClick={() => {
              setNewShortcut([]);
              setEditingShortcut(action);
            }}
          />
        ) : (
          <div className="w-3 h-3" />
        )}
        <KeyboardHotkeys className="justify-end" shortcut={hotkey.key} />
        <span>{hotkey.name.toLowerCase()}</span>
      </div>
    );
  };

  const groups = hotkeys.getHotkeyGroups();
  const renderGroup = (group: HotkeyGroup) => {
    const items = groups[group];
    return (
      <div className="mb-[40px] gap-2 flex flex-col">
        <h3 className="text-lg font-medium">{group}</h3>

        {items.map((item) => renderItem(item))}
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => setIsOpen(open)}>
      {/* Manually portal so we can adjust positioning: shortcuts modal is too large to offset from top for some screens. */}
      <DialogPortal className="sm:items-center sm:top-0">
        <DialogOverlay />
        <DialogContent
          usePortal={false}
          className="max-h-screen sm:max-h-[90vh] overflow-y-auto sm:max-w-[850px]"
        >
          <DialogHeader>
            <DialogTitle>Shortcuts</DialogTitle>
          </DialogHeader>
          <div className="flex flex-row gap-3">
            <div className="w-1/2">
              {renderGroup("Editing")}
              {renderGroup("Markdown")}
            </div>

            <div className="w-1/2">
              {renderGroup("Navigation")}
              {renderGroup("Running Cells")}
              {renderGroup("Creation and Ordering")}
              {renderGroup("Other")}
              <Button
                className="mt-4 hover:bg-destructive/10 hover:border-destructive"
                variant="outline"
                size="xs"
                onClick={handleResetAllShortcuts}
                tabIndex={-1}
              >
                <span className="text-destructive">Reset all to default</span>
              </Button>
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
    </Dialog>
  );
};
