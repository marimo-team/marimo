/* Copyright 2023 Marimo. All rights reserved. */
import React, { memo } from "react";
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
import { SquareEqualIcon, WorkflowIcon } from "lucide-react";
import { Badge } from "../ui/badge";
import { toast } from "../ui/use-toast";

interface Props {
  className?: string;
  /**
   * Used to sort the variables.
   */
  cellIds: CellId[];
  variables: Variables;
}

export const VariableTable: React.FC<Props> = memo(
  ({ className, cellIds, variables }) => {
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
      <Table className={cn("w-full overflow-hidden text-sm flex-1", className)}>
        <TableHeader>
          <TableRow className="whitespace-nowrap text-xs">
            <TableHead>Name</TableHead>
            <TableHead>
              <div className="flex flex-col gap-1">
                <span>Type</span>
                <span>Value</span>
              </div>
            </TableHead>
            <TableHead>
              <div className="flex flex-col gap-1">
                <span>Declared In</span>
                <span>Used By</span>
              </div>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedVariables.map((variable) => (
            <TableRow key={variable.name}>
              <TableCell
                className="font-medium max-w-[130px]"
                title={variable.name}
              >
                <div>
                  <Badge
                    variant={
                      variable.declaredBy.length > 1 ? "destructive" : "success"
                    }
                    className="rounded-sm text-ellipsis block overflow-hidden max-w-fit cursor-pointer"
                    onClick={() => {
                      navigator.clipboard.writeText(variable.name);
                      toast({ title: "Copied to clipboard" });
                    }}
                  >
                    {variable.name}
                  </Badge>
                </div>
              </TableCell>
              <TableCell className="max-w-[150px]">
                <div className="text-ellipsis overflow-hidden whitespace-nowrap text-muted-foreground font-mono text-xs">
                  {variable.dataType}
                </div>
                <div
                  className="text-ellipsis overflow-hidden whitespace-nowrap"
                  title={variable.value}
                >
                  {variable.value}
                </div>
              </TableCell>
              <TableCell className="py-1">
                <div className="flex flex-col gap-1">
                  <div className="flex flex-row overflow-auto gap-2 items-center">
                    <span title="Declared by">
                      <SquareEqualIcon className="w-3.5 h-3.5 text-muted-foreground" />
                    </span>

                    {variable.declaredBy.length === 1 ? (
                      <CellLink cellId={variable.declaredBy[0]} />
                    ) : (
                      <div className="text-destructive flex flex-row gap-2">
                        {variable.declaredBy.slice(0, 3).map((cellId, idx) => (
                          <span className="flex" key={cellId}>
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
                  </div>
                  <div className="flex flex-row overflow-auto gap-2 items-baseline">
                    <span title="Used by">
                      <WorkflowIcon className="w-3.5 h-3.5 text-muted-foreground" />
                    </span>

                    {variable.usedBy.slice(0, 3).map((cellId, idx) => (
                      <span className="flex" key={cellId}>
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
                  </div>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }
);
VariableTable.displayName = "VariableTable";
