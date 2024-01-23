/* Copyright 2024 Marimo. All rights reserved. */
import { useRef } from "react";
import { KeyboardIcon } from "lucide-react";

import { Button } from "@/components/editor/inputs/Inputs";
import { useHotkey } from "../../hooks/useHotkey";
import { Tooltip } from "../ui/tooltip";
import { Kbd } from "../ui/kbd";
import {
  Dialog,
  DialogContent,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogTitle,
} from "../ui/dialog";
import { prettyPrintHotkey, renderShortcut } from "../shortcuts/renderShortcut";
import { HOTKEYS, HotkeyAction, HotkeyGroup } from "@/core/hotkeys/hotkeys";

export const KeyboardShortcuts = (): JSX.Element => {
  const ref = useRef<HTMLButtonElement | null>(null);

  useHotkey("global.showHelp", () => {
    ref.current?.click();
  });

  const renderItem = (action: HotkeyAction) => {
    const hotkey = HOTKEYS.getHotkey(action);
    return (
      <div className="keyboard-shortcut" key={action}>
        <div className="flex gap-1">
          {prettyPrintHotkey(hotkey.key).map((key) => (
            <Kbd key={key}>{key}</Kbd>
          ))}
        </div>
        <span>{hotkey.name.toLowerCase()}</span>
      </div>
    );
  };

  const groups = HOTKEYS.getHotkeyGroups();
  const renderGroup = (group: HotkeyGroup) => {
    const items = groups[group];
    return (
      <div className="keyboard-shortcut-group">
        <h3 className="text-lg font-medium">{group}</h3>

        {items.map((item) => renderItem(item))}
      </div>
    );
  };

  return (
    <Dialog>
      <Tooltip content={renderShortcut("global.showHelp")}>
        <DialogTrigger asChild={true}>
          <Button ref={ref} shape="rectangle" color="white">
            <KeyboardIcon className="help-icon" strokeWidth={1.5} />
          </Button>
        </DialogTrigger>
      </Tooltip>

      {/* Manually portal so we can adjust positioning: shortcuts modal is too large to offset from top for some screens. */}
      <DialogPortal className="sm:items-center sm:top-0">
        <DialogOverlay />
        <DialogContent
          usePortal={false}
          className="max-h-[90vh] overflow-y-auto min-w-[850px]"
        >
          <DialogTitle>Shortcuts</DialogTitle>
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
