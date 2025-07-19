/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import { PopoverClose } from "@radix-ui/react-popover";
import type { Column, ColumnDef } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import { exactDateTime } from "@/utils/dates";
import { Logger } from "@/utils/Logger";
import { Maps } from "@/utils/maps";
import { Objects } from "@/utils/objects";
import { EmotionCacheProvider } from "../editor/output/EmotionCacheProvider";
import { JsonOutput } from "../editor/output/JsonOutput";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import type { ColumnChartSpecModel } from "./chart-spec-model";
import { DataTableColumnHeader } from "./column-header";
import { TableColumnSummary } from "./column-summary";
import { DatePopover } from "./date-popover";
import type { FilterType } from "./filters";
import { getMimeValues, MimeCell } from "./mime-cell";
import {
  type DataTableSelection,
  extractTimezone,
  type FieldTypesWithExternalType,
  INDEX_COLUMN_NAME,
} from "./types";
import { uniformSample } from "./uniformSample";
import { parseContent, UrlDetector } from "./url-detector";

// Artificial limit to display long strings
const MAX_STRING_LENGTH = 50;
const SELECT_ID = "__select__";

function inferDataType(value: unknown): [type: DataType, displayType: string] {
  if (typeof value === "string") {
    return ["string", "string"];
  }
  if (typeof value === "number") {
    return ["number", "number"];
  }
  if (value instanceof Date) {
    return ["datetime", "datetime"];
  }
  if (typeof value === "boolean") {
    return ["boolean", "boolean"];
  }
  if (value == null) {
    return ["unknown", "object"];
  }
  return ["unknown", "object"];
}

export function inferFieldTypes<T>(items: T[]): FieldTypesWithExternalType {
  // No items
  if (items.length === 0) {
    return [];
  }

  // Not an object
  if (typeof items[0] !== "object") {
    return [];
  }

  const fieldTypes: Record<string, [DataType, string]> = {};

  // This can be slow for large datasets,
  // so only sample 10 evenly distributed rows
  uniformSample(items, 10).forEach((item) => {
    if (typeof item !== "object" || item === null) {
      return;
    }
    // We will be a bit defensive and assume values are not homogeneous.
    // If any is a mimetype, then we will treat it as a mimetype (i.e. not sortable)
    Object.entries(item).forEach(([key, value]) => {
      const currentValue = fieldTypes[key];
      if (!currentValue) {
        // Set for the first time
        fieldTypes[key] = inferDataType(value);
      }

      // If its not null, override the type
      if (value != null) {
        // This can be lossy as we infer take the last seen type
        fieldTypes[key] = inferDataType(value);
      }
    });
  });

  return Objects.entries(fieldTypes);
}

export const NAMELESS_COLUMN_PREFIX = "__m_column__";

export function generateColumns<T>({
  rowHeaders,
  selection,
  fieldTypes,
  chartSpecModel,
  textJustifyColumns,
  wrappedColumns,
  showDataTypes,
  calculateTopKRows,
}: {
  rowHeaders: FieldTypesWithExternalType;
  selection: DataTableSelection;
  fieldTypes: FieldTypesWithExternalType;
  chartSpecModel?: ColumnChartSpecModel<unknown>;
  textJustifyColumns?: Record<string, "left" | "center" | "right">;
  wrappedColumns?: string[];
  showDataTypes?: boolean;
  calculateTopKRows?: CalculateTopKRows;
}): Array<ColumnDef<T>> {
  // Row-headers are typically index columns
  const rowHeadersSet = new Set(rowHeaders.map(([columnName]) => columnName));

  const typesByColumn = Maps.keyBy(fieldTypes, (entry) => entry[0]);

  const getMeta = (key: string) => {
    const types = typesByColumn.get(key)?.[1];
    const isRowHeader = rowHeadersSet.has(key);

    if (isRowHeader || !types) {
      const types = rowHeaders.find(([columnName]) => columnName === key)?.[1];
      return {
        rowHeader: isRowHeader,
        dtype: types?.[1],
        dataType: types?.[0],
      };
    }

    return {
      rowHeader: isRowHeader,
      filterType: getFilterTypeForFieldType(types[0]),
      dtype: types[1],
      dataType: types[0],
    };
  };

  const columnKeys: string[] = [
    ...rowHeadersSet,
    ...fieldTypes.map(([columnName]) => columnName),
  ];

  // Remove the index column if it exists
  const indexColumnIdx = columnKeys.indexOf(INDEX_COLUMN_NAME);
  if (indexColumnIdx !== -1) {
    columnKeys.splice(indexColumnIdx, 1);
  }

  const columns = columnKeys.map(
    (key, idx): ColumnDef<T> => ({
      id: key || `${NAMELESS_COLUMN_PREFIX}${idx}`,
      // Use an accessorFn instead of an accessorKey because column names
      // may have periods in them ...
      // https://github.com/TanStack/table/issues/1671
      accessorFn: (row) => {
        return row[key as keyof T];
      },

      header: ({ column }) => {
        const stats = chartSpecModel?.getColumnStats(key);
        const dtype = column.columnDef.meta?.dtype;
        const dtypeHeader =
          showDataTypes && dtype ? (
            <div className="flex flex-row gap-1">
              <span className="text-xs text-muted-foreground">{dtype}</span>
              {stats && typeof stats.nulls === "number" && stats.nulls > 0 && (
                <span className="text-xs text-muted-foreground">
                  (nulls: {stats.nulls})
                </span>
              )}
            </div>
          ) : null;

        const headerWithType = (
          <div className="flex flex-col">
            <span className="font-bold">{key === "" ? " " : key}</span>
            {dtypeHeader}
          </div>
        );

        const dataTableColumnHeader = (
          <DataTableColumnHeader
            header={headerWithType}
            column={column}
            calculateTopKRows={calculateTopKRows}
          />
        );

        // Row headers have no summaries
        if (rowHeadersSet.has(key)) {
          return dataTableColumnHeader;
        }

        return (
          <div className="flex flex-col h-full pt-0.5 pb-3 justify-between items-start">
            {dataTableColumnHeader}
            <TableColumnSummary columnId={key} />
          </div>
        );
      },

      cell: ({ column, renderValue, getValue, cell }) => {
        function selectCell() {
          if (selection !== "single-cell" && selection !== "multi-cell") {
            return;
          }

          cell.toggleSelected?.();
        }

        const justify = textJustifyColumns?.[key];
        const wrapped = wrappedColumns?.includes(key);
        const isCellSelected = cell?.getIsSelected?.() || false;
        const canSelectCell =
          (selection === "single-cell" || selection === "multi-cell") &&
          !isCellSelected;

        const cellStyles = getCellStyleClass(
          justify,
          wrapped,
          canSelectCell,
          isCellSelected,
        );

        const renderedCell = renderCellValue(
          column,
          renderValue,
          getValue,
          selectCell,
          cellStyles,
        );

        // Row headers are bold
        if (rowHeadersSet.has(key)) {
          return <b>{renderedCell}</b>;
        }

        return renderedCell;
      },
      // Remove any default filtering
      filterFn: undefined,
      // Can only sort if key is defined
      // For example, unnamed index columns, won't be sortable
      enableSorting: !!key,
      meta: getMeta(key),
    }),
  );

  if (selection === "single" || selection === "multi") {
    columns.unshift({
      id: SELECT_ID,
      maxSize: 40,
      header: ({ table }) =>
        selection === "multi" ? (
          <Checkbox
            data-testid="select-all-checkbox"
            checked={table.getIsAllPageRowsSelected()}
            onCheckedChange={(value) =>
              table.toggleAllPageRowsSelected(!!value)
            }
            aria-label="Select all"
            className="mx-1.5 my-4"
          />
        ) : null,
      cell: ({ row }) => (
        <Checkbox
          data-testid="select-row-checkbox"
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
          className="mx-2"
          onMouseDown={(e) => {
            // Prevent cell underneath from being selected
            e.stopPropagation();
          }}
        />
      ),
      enableSorting: false,
      enableHiding: false,
    });
  }

  return columns;
}

const PopoutColumn = ({
  cellStyles,
  selectCell,
  rawStringValue,
  contentClassName,
  buttonText,
  children,
}: {
  cellStyles?: string;
  selectCell?: () => void;
  rawStringValue: string;
  contentClassName?: string;
  buttonText?: string;
  children: React.ReactNode;
}) => {
  return (
    <EmotionCacheProvider container={null}>
      <Popover>
        <PopoverTrigger
          className={cn(cellStyles, "w-fit outline-none")}
          onClick={selectCell}
          onMouseDown={(e) => {
            // Prevent cell underneath from being selected
            e.stopPropagation();
          }}
        >
          <span
            className="cursor-pointer hover:text-link"
            title={rawStringValue}
          >
            {rawStringValue}
          </span>
        </PopoverTrigger>
        <PopoverContent
          className={contentClassName}
          align="start"
          alignOffset={10}
        >
          <PopoverClose className="absolute top-2 right-2">
            <Button variant="link" size="xs">
              {buttonText ?? "Close"}
            </Button>
          </PopoverClose>
          {children}
        </PopoverContent>
      </Popover>
    </EmotionCacheProvider>
  );
};

function isPrimitiveOrNullish(value: unknown): boolean {
  if (value == null) {
    return true;
  }
  const isObject = typeof value === "object";
  return !isObject;
}

function getFilterTypeForFieldType(
  type: DataType | undefined,
): FilterType | undefined {
  if (type === undefined) {
    return undefined;
  }
  switch (type) {
    case "string":
      return "text";
    case "number":
      return "number";
    case "integer":
      return "number";
    case "date":
      return "date";
    case "datetime":
      return "datetime";
    case "time":
      return "time";
    case "boolean":
      return "boolean";
    default:
      return undefined;
  }
}

function getCellStyleClass(
  justify: "left" | "center" | "right" | undefined,
  wrapped: boolean | undefined,
  canSelectCell: boolean,
  isSelected: boolean,
): string {
  return cn(
    canSelectCell && "cursor-pointer",
    isSelected &&
      "relative before:absolute before:inset-0 before:bg-[var(--blue-3)] before:rounded before:-z-10 before:mx-[-4px] before:my-[-2px]",
    "w-full",
    "text-left",
    "truncate",
    justify === "center" && "text-center",
    justify === "right" && "text-right",
    wrapped && "whitespace-pre-wrap min-w-[200px] break-words",
  );
}

function renderAny(value: unknown): string {
  if (value == null) {
    return "";
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function renderDate(
  value: Date,
  dataType?: DataType,
  dtype?: string,
): React.ReactNode {
  const type = dataType === "date" ? "date" : "datetime";
  const timezone = extractTimezone(dtype);
  return (
    <DatePopover date={value} type={type}>
      {exactDateTime(value, timezone)}
    </DatePopover>
  );
}

export function renderCellValue<TData, TValue>(
  column: Column<TData, TValue>,
  renderValue: () => TValue | null,
  getValue: () => TValue,
  selectCell?: () => void,
  cellStyles?: string,
) {
  const value = getValue();
  const format = column.getColumnFormatting?.();

  const dataType = column.columnDef.meta?.dataType;
  const dtype = column.columnDef.meta?.dtype;

  if (dataType === "datetime" && typeof value === "string") {
    try {
      const date = new Date(value);
      return renderDate(date, dataType, dtype);
    } catch (error) {
      Logger.error("Error parsing datetime, fallback to string", error);
    }
  }

  if (value instanceof Date) {
    // e.g. 2010-10-07 17:15:00
    return renderDate(value, dataType, dtype);
  }

  if (typeof value === "string") {
    const stringValue = format
      ? String(column.applyColumnFormatting(value))
      : String(renderValue());

    const parts = parseContent(stringValue);
    const hasMarkup = parts.some((part) => part.type !== "text");
    if (hasMarkup || stringValue.length < MAX_STRING_LENGTH) {
      return (
        <div onClick={selectCell} className={cellStyles}>
          <UrlDetector parts={parts} />
        </div>
      );
    }

    return (
      <PopoutColumn
        cellStyles={cellStyles}
        selectCell={selectCell}
        rawStringValue={stringValue}
        contentClassName="max-h-64 overflow-auto whitespace-pre-wrap break-words text-sm"
        buttonText="X"
      >
        <UrlDetector parts={parts} />
      </PopoutColumn>
    );
  }

  if (format) {
    return (
      <div onClick={selectCell} className={cellStyles}>
        {column.applyColumnFormatting(value)}
      </div>
    );
  }

  if (isPrimitiveOrNullish(value)) {
    const rendered = renderValue();
    return (
      <div onClick={selectCell} className={cellStyles}>
        {rendered == null ? "" : String(rendered)}
      </div>
    );
  }

  const mimeValues = getMimeValues(value);
  if (mimeValues) {
    return (
      <div onClick={selectCell} className={cellStyles}>
        {mimeValues.map((mimeValue, idx) => (
          <MimeCell key={idx} value={mimeValue} />
        ))}
      </div>
    );
  }

  if (Array.isArray(value) || typeof value === "object") {
    const rawStringValue = renderAny(value);
    return (
      <PopoutColumn
        cellStyles={cellStyles}
        selectCell={selectCell}
        rawStringValue={rawStringValue}
      >
        <JsonOutput data={value} format="tree" className="max-h-64" />
      </PopoutColumn>
    );
  }

  return (
    <div onClick={selectCell} className={cellStyles}>
      {renderAny(value)}
    </div>
  );
}
