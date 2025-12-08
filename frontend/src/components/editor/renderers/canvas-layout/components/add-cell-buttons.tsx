/* Copyright 2024 Marimo. All rights reserved. */

import { PlusIcon } from "lucide-react";
import React, { memo } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import { AddCellMenuItems } from "./add-cell-menu-items";

interface AddCellButtonsProps {
  cellId: CellId;
  nodePosition?: { x: number; y: number };
  nodeSize?: { width: number; height: number };
}

export const AddCellButtons: React.FC<AddCellButtonsProps> = memo(
  ({ cellId, nodePosition, nodeSize }) => {
    const buttonClass =
      "absolute z-30 transition-all duration-200 pointer-events-auto w-7 h-7 p-0 rounded-full bg-primary/10 hover:bg-primary/20 border-2 border-primary/30 hover:border-primary hover:scale-110 opacity-0";

    const hoverAreaClass = "absolute pointer-events-auto";

    return (
      <>
        {/* Top hover area + button */}
        <div
          className={cn(
            hoverAreaClass,
            "left-0 right-0 -top-[40px] h-[40px] group/top",
          )}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                className={cn(
                  buttonClass,
                  "left-1/2 -translate-x-1/2 top-[6px] group-hover/top:opacity-100",
                )}
                title="Add cell above"
              >
                <PlusIcon className="h-3 w-3 text-primary" strokeWidth={3} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top">
              <AddCellMenuItems
                direction="above"
                cellId={cellId}
                nodePosition={nodePosition}
                nodeSize={nodeSize}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Bottom hover area + button */}
        <div
          className={cn(
            hoverAreaClass,
            "left-0 right-0 -bottom-[40px] h-[40px] group/bottom",
          )}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                className={cn(
                  buttonClass,
                  "left-1/2 -translate-x-1/2 bottom-[6px] group-hover/bottom:opacity-100",
                )}
                title="Add cell below"
              >
                <PlusIcon className="h-3 w-3 text-primary" strokeWidth={3} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="bottom">
              <AddCellMenuItems
                direction="below"
                cellId={cellId}
                nodePosition={nodePosition}
                nodeSize={nodeSize}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Left hover area + button */}
        <div
          className={cn(
            hoverAreaClass,
            "top-0 bottom-0 -left-[40px] w-[40px] group/left",
          )}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                className={cn(
                  buttonClass,
                  "top-1/2 -translate-y-1/2 left-[6px] group-hover/left:opacity-100",
                )}
                title="Add cell to the left"
              >
                <PlusIcon className="h-3 w-3 text-primary" strokeWidth={3} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="left">
              <AddCellMenuItems
                direction="left"
                cellId={cellId}
                nodePosition={nodePosition}
                nodeSize={nodeSize}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Right hover area + button */}
        <div
          className={cn(
            hoverAreaClass,
            "top-0 bottom-0 -right-[40px] w-[40px] group/right",
          )}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="icon"
                variant="outline"
                className={cn(
                  buttonClass,
                  "top-1/2 -translate-y-1/2 right-[6px] group-hover/right:opacity-100",
                )}
                title="Add cell to the right"
              >
                <PlusIcon className="h-3 w-3 text-primary" strokeWidth={3} />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="right">
              <AddCellMenuItems
                direction="right"
                cellId={cellId}
                nodePosition={nodePosition}
                nodeSize={nodeSize}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </>
    );
  },
);

AddCellButtons.displayName = "AddCellButtons";
