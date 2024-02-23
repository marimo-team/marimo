/* Copyright 2024 Marimo. All rights reserved. */
import { Fragment, useState } from "react";

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  TooltipContent,
  TooltipRoot,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { renderMinimalShortcut } from "@/components/shortcuts/renderShortcut";
import React from "react";
import {
  CellActionButtonProps,
  useCellActionButtons,
} from "../actions/useCellActionButton";

interface Props extends CellActionButtonProps {
  children: React.ReactNode;
}

export const CellActionsDropdown = ({ children, ...props }: Props) => {
  const [open, setOpen] = useState(false);
  const actions = useCellActionButtons(props);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <TooltipRoot delayDuration={400} disableHoverableContent={true}>
        {!open && (
          <TooltipContent className="w-full bg-card" tabIndex={-1}>
            <div className="text-foreground-muted flex flex-col text-center">
              <span>
                <span className="text-foreground font-semibold">Drag </span>to
                move cell
              </span>
              <span>
                <span className="text-foreground font-semibold">Click </span>to
                open menu
              </span>
            </div>
          </TooltipContent>
        )}
        {/* This creates a warning in React due to nested <button> elements.
        Adding asChild could fix this, but it also changes the styling (is hidden) of the button when
        the Popover is open. */}
        <TooltipTrigger>
          <PopoverTrigger className="flex">{children}</PopoverTrigger>
        </TooltipTrigger>
      </TooltipRoot>
      <PopoverContent
        className="w-[300px] p-0 pt-1"
        onOpenAutoFocus={(e) => e.preventDefault()}
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <Command>
          <CommandInput
            placeholder="Search actions..."
            className="h-6 m-1"
            autoFocus={true}
          />
          <CommandEmpty>No results</CommandEmpty>
          {actions.map((group, i) => (
            <Fragment key={i}>
              <CommandGroup key={i}>
                {group.map((action) => {
                  return (
                    <CommandItem
                      key={action.label}
                      onSelect={() => {
                        if (action.disableClick) {
                          return;
                        }
                        action.handle();
                        setOpen(false);
                      }}
                      variant={action.variant}
                    >
                      <div className="flex items-center flex-1">
                        {action.icon && (
                          <div className="mr-2 w-5">{action.icon}</div>
                        )}
                        <div className="flex-1">{action.label}</div>
                        <div className="flex-shrink-0 text-sm">
                          {action.hotkey &&
                            renderMinimalShortcut(action.hotkey)}
                          {action.rightElement}
                        </div>
                      </div>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
              {i < actions.length - 1 && <CommandSeparator />}
            </Fragment>
          ))}
        </Command>
      </PopoverContent>
    </Popover>
  );
};
