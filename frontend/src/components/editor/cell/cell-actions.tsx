/* Copyright 2024 Marimo. All rights reserved. */
import {
  Fragment,
  type PropsWithChildren,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";

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
  type CellActionButtonProps,
  useCellActionButtons,
} from "../actions/useCellActionButton";
import { useRestoreFocus } from "@/components/ui/use-restore-focus";
import { useAtomValue } from "jotai";
import { cellFocusDetailsAtom } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import { CommandList } from "cmdk";

interface Props extends CellActionButtonProps {
  children: React.ReactNode;
  showTooltip?: boolean;
}

export interface CellActionsDropdownHandle {
  toggle: () => void;
}

const CellActionsDropdownInternal = (
  { children, showTooltip = true, ...props }: Props,
  ref: React.Ref<CellActionsDropdownHandle>,
) => {
  const [open, setOpen] = useState(false);
  const actions = useCellActionButtons({ cell: props });

  // store the last focused element so we can restore it when the popover closes
  const restoreFocus = useRestoreFocus();

  useImperativeHandle(ref, () => ({
    toggle: () => setOpen((prev) => !prev),
  }));

  const content = (
    <PopoverContent className="w-[300px] p-0 pt-1" {...restoreFocus}>
      <Command>
        <CommandInput placeholder="Search actions..." className="h-6 m-1" />
        <CommandList>
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
        </CommandList>
      </Command>
    </PopoverContent>
  );

  if (!showTooltip) {
    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild={true}>{children}</PopoverTrigger>
        {content}
      </Popover>
    );
  }

  const tooltipContent = (
    <TooltipContent className="w-full bg-card" tabIndex={-1}>
      <div className="text-foreground-muted flex flex-col text-center">
        <span>
          <span className="text-foreground font-semibold">Drag </span>to move
          cell
        </span>
        <span>
          <span className="text-foreground font-semibold">Click </span>to open
          menu
        </span>
      </div>
    </TooltipContent>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <TooltipRoot delayDuration={400} disableHoverableContent={true}>
        {!open && tooltipContent}
        {/* This creates a warning in React due to nested <button> elements.
        Adding asChild could fix this, but it also changes the styling (is hidden) of the button when
        the Popover is open. */}
        <TooltipTrigger>
          <PopoverTrigger className="flex">{children}</PopoverTrigger>
        </TooltipTrigger>
      </TooltipRoot>
      {content}
    </Popover>
  );
};

export const CellActionsDropdown = React.memo(
  React.forwardRef(CellActionsDropdownInternal),
);

export const ConnectionCellActionsDropdown = React.memo(
  ({ children, cellId }: PropsWithChildren<{ cellId: CellId }>) => {
    const state = useAtomValue(
      useMemo(() => cellFocusDetailsAtom(cellId), [cellId]),
    );

    if (!state) {
      return null;
    }

    return (
      <CellActionsDropdown showTooltip={false} {...state}>
        {children}
      </CellActionsDropdown>
    );
  },
);
ConnectionCellActionsDropdown.displayName = "ConnectionCellActionsDropdown";
