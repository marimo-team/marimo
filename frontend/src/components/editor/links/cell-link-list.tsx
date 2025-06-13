/* Copyright 2024 Marimo. All rights reserved. */

import type React from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useCellIds } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { CellLink } from "./cell-link";

interface Props {
  maxCount: number;
  cellIds: CellId[];
  skipScroll?: boolean;
  onClick?: (cellId: CellId) => void;
}

export const CellLinkList: React.FC<Props> = ({
  maxCount,
  cellIds,
  onClick,
  skipScroll,
}) => {
  const cellIndex = useCellIds();
  const sortedCellIds = [...cellIds].sort((a, b) => {
    return cellIndex.inOrderIds.indexOf(a) - cellIndex.inOrderIds.indexOf(b);
  });

  if (cellIds.length === 0) {
    return <div className="text-muted-foreground">--</div>;
  }

  return (
    <>
      {sortedCellIds.slice(0, maxCount).map((cellId, idx) => (
        <span className="truncate" key={cellId}>
          <CellLink
            variant="focus"
            key={cellId}
            cellId={cellId}
            skipScroll={skipScroll}
            className="whitespace-nowrap"
            onClick={onClick ? () => onClick(cellId) : undefined}
          />
          {idx < cellIds.length - 1 && ", "}
        </span>
      ))}
      {cellIds.length > maxCount && (
        <Popover>
          <PopoverTrigger asChild={true}>
            <span className="whitespace-nowrap text-muted-foreground text-xs hover:underline cursor-pointer">
              +{cellIds.length - maxCount} more
            </span>
          </PopoverTrigger>
          <PopoverContent className="w-auto">
            <div className="flex flex-col gap-1 py-1">
              {sortedCellIds.slice(maxCount).map((cellId) => (
                <CellLink
                  variant="focus"
                  key={cellId}
                  cellId={cellId}
                  className="whitespace-nowrap"
                  onClick={onClick ? () => onClick(cellId) : undefined}
                />
              ))}
            </div>
          </PopoverContent>
        </Popover>
      )}
    </>
  );
};
