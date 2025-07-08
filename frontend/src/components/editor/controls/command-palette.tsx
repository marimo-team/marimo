/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtom, useAtomValue } from "jotai";
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
import { lastFocusedCellAtom } from "@/core/cells/focus";
import { hotkeysAtom } from "@/core/config/config";
import { type HotkeyAction, isHotkeyAction } from "@/core/hotkeys/hotkeys";
import { parseShortcut } from "@/core/hotkeys/shortcuts";
import { useEventListener } from "@/hooks/useEventListener";
import { Objects } from "@/utils/objects";
import { useRegisteredActions } from "../../../core/hotkeys/actions";
import { useRecentCommands } from "../../../hooks/useRecentCommands";
import { KeyboardHotkeys } from "../../shortcuts/renderShortcut";
import {
  type ActionButton,
  flattenActions,
  isParentAction,
} from "../actions/types";
import { useCellActionButtons } from "../actions/useCellActionButton";
import { useConfigActions } from "../actions/useConfigActions";
import { useNotebookActions } from "../actions/useNotebookActions";

export const commandPaletteAtom = atom(false);

export const CommandPalette = () => {
  const [open, setOpen] = useAtom(commandPaletteAtom);
  const registeredActions = useRegisteredActions();
  const lastFocusedCell = useAtomValue(lastFocusedCellAtom);
  const hotkeys = useAtomValue(hotkeysAtom);
  // Cell actions
  let cellActions = useCellActionButtons({ cell: lastFocusedCell }).flat();
  cellActions = flattenActions(cellActions);
  // Notebook actions
  const configActions = useConfigActions();
  let notebookActions = useNotebookActions();
  notebookActions = [
    ...flattenActions(notebookActions),
    ...flattenActions(configActions),
  ];

  const notebookActionsWithoutHotkeys = notebookActions.filter(
    (action) => !action.hotkey,
  );
  const keyedNotebookActions: Record<string, ActionButton | undefined> =
    Objects.keyBy(notebookActionsWithoutHotkeys, (action) => action.label);

  const { recentCommands, addRecentCommand } = useRecentCommands();
  const recentCommandsSet = new Set(recentCommands);

  useEventListener(document, "keydown", (e) => {
    if (parseShortcut(hotkeys.getHotkey("global.commandPalette").key)(e)) {
      e.preventDefault();
      setOpen((open) => !open);
    }
  });

  const renderShortcutCommandItem = (
    shortcut: HotkeyAction,
    props: {
      disabled?: boolean;
      tooltip?: React.ReactNode;
    },
  ) => {
    const action = registeredActions[shortcut];
    if (!action) {
      return null;
    }
    const hotkey = hotkeys.getHotkey(shortcut);

    return (
      <CommandItem
        disabled={props.disabled}
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
        <span>
          {hotkey.name}
          {props.tooltip && <span className="ml-2">{props.tooltip}</span>}
        </span>
        <CommandShortcut>
          <KeyboardHotkeys shortcut={hotkey.key} />
        </CommandShortcut>
      </CommandItem>
    );
  };

  const renderCommandItem = ({
    label,
    handle,
    props = {},
    hotkey,
  }: {
    label: string;
    handle: () => void;
    props?: { disabled?: boolean; tooltip?: React.ReactNode };
    hotkey?: HotkeyAction;
  }) => {
    return (
      <CommandItem
        disabled={props.disabled}
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
        <span>
          {label}
          {props.tooltip && <span className="ml-2">({props.tooltip})</span>}
        </span>
        {hotkey && (
          <CommandShortcut>
            <KeyboardHotkeys shortcut={hotkeys.getHotkey(hotkey).key} />
          </CommandShortcut>
        )}
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
                const action = keyedNotebookActions[shortcut];
                // Hotkey
                if (isHotkeyAction(shortcut)) {
                  return renderShortcutCommandItem(shortcut, {
                    disabled: action?.disabled,
                    tooltip: action?.tooltip,
                  });
                }
                // Other action
                if (action && !isParentAction(action)) {
                  return renderCommandItem({
                    label: action.label,
                    handle: action.handleHeadless || action.handle,
                    props: {
                      disabled: action.disabled,
                      tooltip: action.tooltip,
                    },
                  });
                }
                return null;
              })}
            </CommandGroup>
            <CommandSeparator />
          </>
        )}
        <CommandGroup heading="Commands">
          {hotkeys.iterate().map((shortcut) => {
            if (recentCommandsSet.has(shortcut)) {
              return null; // Don't show recent commands in the main list
            }
            const action = keyedNotebookActions[shortcut];
            return renderShortcutCommandItem(shortcut, {
              disabled: action?.disabled,
              tooltip: action?.tooltip,
            });
          })}
          {notebookActionsWithoutHotkeys.map((action) => {
            if (recentCommandsSet.has(action.label)) {
              return null; // Don't show recent commands in the main list
            }
            return renderCommandItem({
              label: action.label,
              handle: action.handleHeadless || action.handle,
              props: { disabled: action.disabled, tooltip: action.tooltip },
            });
          })}
          {cellActions.map((action) => {
            if (recentCommandsSet.has(action.label)) {
              return null; // Don't show recent commands in the main list
            }
            return renderCommandItem({
              label: `Cell > ${action.label}`,
              handle: action.handleHeadless || action.handle,
              props: { disabled: action.disabled, tooltip: action.tooltip },
            });
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
};
