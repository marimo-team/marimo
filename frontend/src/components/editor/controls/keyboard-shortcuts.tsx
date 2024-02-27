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
import { HOTKEYS, HotkeyAction, HotkeyGroup } from "@/core/hotkeys/hotkeys";
import { atom, useAtom } from "jotai";

export const keyboardShortcutsAtom = atom(false);

export const KeyboardShortcuts: React.FC = () => {
  const [isOpen, setIsOpen] = useAtom(keyboardShortcutsAtom);

  useHotkey("global.showHelp", () => setIsOpen((v) => !v));

  if (!isOpen) {
    return null;
  }

  const renderItem = (action: HotkeyAction) => {
    const hotkey = HOTKEYS.getHotkey(action);
    return (
      <div className="keyboard-shortcut flex flex-col" key={action}>
        <KeyboardHotkeys shortcut={hotkey.key} />
        <span>{hotkey.name.toLowerCase()}</span>
      </div>
    );
  };

  const groups = HOTKEYS.getHotkeyGroups();
  const renderGroup = (group: HotkeyGroup) => {
    const items = groups[group];
    return (
      <div className="keyboard-shortcut-group gap-2 flex flex-col">
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
              {renderGroup("Navigation")}
            </div>

            <div className="w-1/2">
              {renderGroup("Running Cells")}
              {renderGroup("Creation and Ordering")}
              {renderGroup("Other")}
            </div>
          </div>
        </DialogContent>
      </DialogPortal>
    </Dialog>
  );
};
