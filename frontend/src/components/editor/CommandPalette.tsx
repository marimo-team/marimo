/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useRegisteredActions } from "../../core/hotkeys/actions";
import { useRecentCommands } from "../../hooks/useRecentCommands";
import { Kbd } from "../ui/kbd";
import { prettyPrintHotkey } from "../shortcuts/renderShortcut";
import { HOTKEYS, HotkeyAction, isHotkeyAction } from "@/core/hotkeys/hotkeys";
import { atom, useAtom } from "jotai";
import { useNotebookActions } from "./actions/useNotebookActions";
import { Objects } from "@/utils/objects";
import { parseShortcut } from "@/core/hotkeys/shortcuts";

export const commandPaletteAtom = atom(false);

export const CommandPalette = () => {
  const [open, setOpen] = useAtom(commandPaletteAtom);
  const registeredActions = useRegisteredActions();
  const notebookActions = useNotebookActions();
  const notebookActionsWithoutHotkeys = notebookActions.filter(
    (action) => !action.hotkey,
  );
  const keyedNotebookActions = Objects.keyBy(
    notebookActionsWithoutHotkeys,
    (action) => action.label,
  );

  const { recentCommands, addRecentCommand } = useRecentCommands();
  const recentCommandsSet = new Set(recentCommands);

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (parseShortcut(HOTKEYS.getHotkey("global.commandPalette").key)(e)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [setOpen]);

  const renderShortcutCommandItem = (shortcut: HotkeyAction) => {
    const action = registeredActions[shortcut];
    if (!action) {
      return null;
    }
    const hotkey = HOTKEYS.getHotkey(shortcut);

    return (
      <CommandItem
        onSelect={() => {
          addRecentCommand(shortcut);
          // Close first and then run the action, so the dialog doesn't steal focus
          setOpen(false);
          requestAnimationFrame(() => {
            action();
          });
        }}
        key={shortcut}
        value={hotkey.name}
      >
        <span>{hotkey.name}</span>
        <CommandShortcut>
          <span className="flex ml-2 gap-1">
            {prettyPrintHotkey(hotkey.key).map((key) => (
              <Kbd key={key}>{key}</Kbd>
            ))}
          </span>
        </CommandShortcut>
      </CommandItem>
    );
  };

  const renderCommandItem = (label: string, handle: () => void) => {
    return (
      <CommandItem
        onSelect={() => {
          addRecentCommand(label);
          setOpen(false);
          requestAnimationFrame(() => {
            handle();
          });
        }}
        key={label}
        value={label}
      >
        <span>{label}</span>
      </CommandItem>
    );
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type to search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        {recentCommands.length > 0 && (
          <>
            <CommandGroup heading="Recently Used">
              {recentCommands.map((shortcut) => {
                // Hotkey
                if (isHotkeyAction(shortcut)) {
                  return renderShortcutCommandItem(shortcut);
                }
                // Other action
                const action = keyedNotebookActions[shortcut];
                if (action) {
                  return renderCommandItem(action.label, action.handle);
                }
                return null;
              })}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}
        <CommandGroup heading="Commands">
          {HOTKEYS.iterate().map((shortcut) => {
            if (recentCommandsSet.has(shortcut)) {
              return null; // Don't show recent commands in the main list
            }
            return renderShortcutCommandItem(shortcut);
          })}
          {notebookActionsWithoutHotkeys.map((action) => {
            if (recentCommandsSet.has(action.label)) {
              return null; // Don't show recent commands in the main list
            }
            return renderCommandItem(action.label, action.handle);
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
};
