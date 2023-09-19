/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import {
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
  Table,
} from "../ui/table";
import { Variables } from "@/core/variables/types";
import { CellId } from "@/core/model/ids";
import { CellLink } from "@/editor/links/cell-link";
import { cn } from "@/lib/utils";

interface Props {
  className?: string;
  /**
   * Used to sort the variables.
   */
  cellIds: CellId[];
  variables: Variables;
}

export const VariableTable: React.FC<Props> = ({
  className,
  cellIds,
  variables,
}) => {
  const cellIdToIndex = new Map<CellId, number>();
  cellIds.forEach((id, index) => cellIdToIndex.set(id, index));

  const sortedVariables = Object.values(variables).sort((a, b) => {
    const aIndex = cellIdToIndex.get(a.declaredBy[0]);
    const bIndex = cellIdToIndex.get(b.declaredBy[0]);
    if (aIndex === undefined || bIndex === undefined) {
      return 0;
    }
    return aIndex - bIndex;
  });

  return (
    <Table className={cn("w-full overflow-hidden text-sm", className)}>
      <TableHeader>
        <TableRow className="whitespace-nowrap">
          <TableHead>Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Declared In</TableHead>
          <TableHead>Used By</TableHead>
          <TableHead>Value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedVariables.map((variable) => (
          <TableRow key={variable.name}>
            <TableCell
              className="font-medium max-w-[200px] text-ellipsis overflow-hidden"
              title={variable.name}
            >
              {variable.name}
            </TableCell>
            <TableCell className="font-medium max-w-[200px] text-ellipsis overflow-hidden">
              {variable.dataType}
            </TableCell>
            <TableCell>
              {variable.declaredBy.length === 1 ? (
                <CellLink cellId={variable.declaredBy[0]} />
              ) : (
                <div className="text-destructive flex flex-row gap-2">
                  {variable.declaredBy.slice(0, 3).map((cellId, idx) => (
                    <span key={cellId}>
                      <CellLink
                        key={cellId}
                        cellId={cellId}
                        className="whitespace-nowrap text-destructive"
                      />
                      {idx < variable.declaredBy.length - 1 && ", "}
                    </span>
                  ))}
                </div>
              )}
            </TableCell>
            <TableCell className="flex flex-row overflow-auto gap-2 items-baseline">
              {variable.usedBy.slice(0, 3).map((cellId, idx) => (
                <span key={cellId}>
                  <CellLink
                    key={cellId}
                    cellId={cellId}
                    className="whitespace-nowrap"
                  />
                  {idx < variable.usedBy.length - 1 && ", "}
                </span>
              ))}
              {variable.usedBy.length > 3 && (
                <div className="whitespace-nowrap text-muted-foreground text-xs">
                  +{variable.usedBy.length - 3} more
                </div>
              )}
            </TableCell>
            <TableCell className="font-medium max-w-[200px] text-ellipsis overflow-hidden">
              {variable.value}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};
