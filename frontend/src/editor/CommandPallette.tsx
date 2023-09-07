/* Copyright 2023 Marimo. All rights reserved. */
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
import { useRegisteredActions } from "../core/state/actions";
import { useRecentCommands } from "../hooks/useRecentCommands";
import { Kbd } from "../components/ui/kbd";
import { prettyPrintHotkey } from "../components/shortcuts/renderShortcut";
import { HOTKEYS, HotkeyAction } from "@/core/hotkeys/hotkeys";
import { atom, useAtom } from "jotai";

export const commandPalletteAtom = atom(false);

export const CommandPallette = () => {
  const [open, setOpen] = useAtom(commandPalletteAtom);
  const registeredActions = useRegisteredActions();
  const { recentCommands, addRecentCommand } = useRecentCommands();

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [setOpen]);

  const renderShortcutCommandItemIfNotRecent = (shortcut: HotkeyAction) => {
    const isRecent = recentCommands.includes(shortcut);
    if (isRecent) {
      return null;
    }
    return renderShortcutCommandItem(shortcut);
  };

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

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type to search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        {recentCommands.length > 0 && (
          <>
            <CommandGroup heading="Recently Used">
              {recentCommands.map((shortcut) =>
                renderShortcutCommandItem(shortcut)
              )}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}
        <CommandGroup heading="Commands">
          {HOTKEYS.iterate().map((shortcut) =>
            renderShortcutCommandItemIfNotRecent(shortcut)
          )}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
};
