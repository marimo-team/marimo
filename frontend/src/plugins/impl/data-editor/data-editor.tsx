/* Copyright 2024 Marimo. All rights reserved. */
import React, { useCallback, useEffect, useMemo, useRef } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  ColDef,
  GridReadyEvent,
  CellEditingStoppedEvent,
  RowDataTransaction,
} from "ag-grid-community";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import { cn } from "@/utils/cn";
import { useTheme } from "@/theme/useTheme";
import type { DataType } from "../vega/vega-loader";
import { Button } from "@/components/ui/button";
import { PlusIcon } from "lucide-react";

export interface DataEditorProps<T> {
  data: T[];
  pagination: boolean;
  pageSize: number;
  fieldTypes: FieldTypesWithExternalType | null | undefined;
  edits: Array<{
    rowIdx: number;
    columnId: string;
    value: unknown;
  }>;
  onAddEdits: (
    edits: Array<{
      rowIdx: number;
      columnId: string;
      value: unknown;
    }>,
  ) => void;
  onAddRows: (newRows: object[]) => void;
  columnSizingMode: "fit" | "auto";
}

function cellEditorForDataType(dataType: DataType) {
  switch (dataType) {
    case "string":
      return "agTextCellEditor";
    case "number":
      return "agNumberCellEditor";
    case "boolean":
      return "agCheckboxCellEditor";
    // TODO: not working properly
    // case "date":
    // case "datetime":
    // case "time":
    //   return 'agDateCellEditor';
    default:
      return "agTextCellEditor";
  }
}

function getHeaderKeys(data: object[]) {
  if (data.length === 0) {
    return [];
  }
  return Object.keys(data[0]);
}

const DataEditor: React.FC<DataEditorProps<object>> = ({
  data,
  edits,
  pagination,
  pageSize,
  fieldTypes,
  onAddEdits,
  onAddRows,
  columnSizingMode,
}) => {
  const { theme } = useTheme();
  const gridRef = useRef<AgGridReact>(null);
  const headerKeys = useMemo(() => {
    if (fieldTypes) {
      return fieldTypes.map(([columnName]) => columnName);
    }
    return getHeaderKeys(data);
  }, [data, fieldTypes]);

  const finalRowData = useMemo(() => {
    for (const edit of edits) {
      if (edit.rowIdx >= data.length) {
        // Add a new row if rowIndex is out of bounds
        const newRow = { [edit.columnId]: edit.value };
        data.push(newRow);
      } else {
        const row = data[edit.rowIdx];
        (row as Record<string, unknown>)[edit.columnId] = edit.value;
      }
    }
    return data;
  }, [data, edits]);

  const columnDefs = useMemo(() => {
    const defs: ColDef[] = [];
    for (const header of headerKeys) {
      defs.push({
        field: header,
        editable: true,
        sortable: false,
        filter: false,
        cellEditorSelector: (params) => {
          const colId = params.column.getColId();
          const dataType: DataType =
            fieldTypes?.find(
              ([columnName]) => columnName === colId,
            )?.[1]?.[0] || "string";
          if (dataType) {
            if (typeof params.value === "string" && params.value.length > 60) {
              return { component: "agLargeTextCellEditor", popup: true };
            }
            return { component: cellEditorForDataType(dataType) };
          }
          return;
        },
      });
    }
    return defs;
  }, [headerKeys, fieldTypes]);

  const defaultColDef = useMemo<ColDef>(() => {
    return {
      sortable: true,
      filter: true,
      minWidth: 100, // Add minimum width to ensure columns are readable
    };
  }, []);

  const sizeColumns = useCallback(() => {
    // Size the columns to either fit the grid or auto-size based on content
    const api = gridRef.current?.api;
    if (!api) {
      return;
    }

    if (columnSizingMode === "fit") {
      api.sizeColumnsToFit();
    } else if (columnSizingMode === "auto") {
      api.autoSizeAllColumns();
    }
  }, [columnSizingMode]);

  const onGridReady = useCallback(
    (params: GridReadyEvent) => {
      sizeColumns();
    },
    [sizeColumns],
  );

  useEffect(() => {
    // Update grid layout when column sizing prop changes
    sizeColumns();
  }, [columnSizingMode, sizeColumns]);

  const onCellEditingStopped = useCallback(
    (event: CellEditingStoppedEvent) => {
      if (!event.valueChanged || event.rowIndex === null) {
        return;
      }
      const edit = {
        rowIdx: event.rowIndex,
        columnId: event.column.getColId(),
        value: event.newValue,
      };
      onAddEdits([edit]);
    },
    [onAddEdits],
  );

  const totalRows = data.length;
  const needsPagination = pagination && totalRows > pageSize;

  const handleAddRow = useCallback(() => {
    const newRow = Object.fromEntries(
      headerKeys.map((key) => {
        const dataType: DataType =
          fieldTypes?.find(([columnName]) => columnName === key)?.[1]?.[0] ||
          "string";
        switch (dataType) {
          case "boolean":
            return [key, false];
          case "integer":
          case "number":
            return [key, 0];
          case "date":
            return [key, new Date()];
          default:
            return [key, ""];
        }
      }),
    );
    onAddRows([newRow]);

    // Update the grid with the new row
    const transaction: RowDataTransaction = {
      add: [newRow],
      addIndex: finalRowData.length,
    };
    gridRef.current?.api.applyTransaction(transaction);
  }, [fieldTypes, onAddRows, headerKeys, finalRowData]);

  return (
    <div
      className={cn(
        theme === "dark" ? "ag-theme-quartz-dark" : "ag-theme-quartz",
        "ag-theme-marimo flex h-[400px] flex-col",
        "relative",
      )}
    >
      <AgGridReact
        ref={gridRef}
        rowData={finalRowData}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        cellSelection={true}
        pagination={needsPagination}
        paginationPageSize={pageSize}
        onGridReady={onGridReady}
        undoRedoCellEditing={true}
        stopEditingWhenCellsLoseFocus={true}
        onCellEditingStopped={onCellEditingStopped}
        animateRows={false}
        singleClickEdit={true}
        suppressFieldDotNotation={true}
        headerHeight={40}
        rowHeight={35}
      />
      <div className="p-2 border-t flex justify-end">
        <Button variant="text" size="xs" onClick={handleAddRow}>
          <PlusIcon className="w-3 h-3 mr-1" />
          Add Row
        </Button>
      </div>
    </div>
  );
};

export default DataEditor;
