/* Copyright 2023 Marimo. All rights reserved. */
import React from 'react'
import { TableHeader, TableRow, TableHead, TableBody, TableCell, Table } from '../ui/table';
import { Variables } from '@/core/variables/types';
import { CellId } from '@/core/model/ids';
import { CellLink } from '@/editor/links/cell-link';
import { cn } from '@/lib/utils';

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
    const aIndex = cellIdToIndex.get(a.declaredBy);
    const bIndex = cellIdToIndex.get(b.declaredBy);
    if (aIndex === undefined || bIndex === undefined) {
      return 0;
    }
    return aIndex - bIndex;
  });

  return (
    <Table className={cn("w-full overflow-hidden", className)}>
      <TableHeader>
        <TableRow className='whitespace-nowrap'>
          <TableHead>Name</TableHead>
          <TableHead>Declared In</TableHead>
          <TableHead>Used By</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedVariables.map((variable) => (
          <TableRow key={variable.name}>
            <TableCell className="font-medium max-w-[200px] text-ellipsis overflow-hidden"
              title={variable.name}
            >{variable.name}</TableCell>
            <TableCell>
              <CellLink cellId={variable.declaredBy} />
            </TableCell>
            <TableCell className="flex flex-row overflow-auto">
              {variable.usedBy.slice(0, 3).map((cellId, idx) => (
                <React.Fragment key={cellId}>
                  <CellLink
                    key={cellId}
                    cellId={cellId}
                    className="ml-2 whitespace-nowrap"
                  />
                  {idx < variable.usedBy.length - 1 && ", "}
                </React.Fragment>
              ))}
              {variable.usedBy.length > 3 && (
                <div className="ml-2 whitespace-nowrap text-muted-foreground text-sm">
                  +{variable.usedBy.length - 3} more
                </div>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
