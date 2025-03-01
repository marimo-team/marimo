/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { ColumnDef } from "@tanstack/react-table";
import {
  DataTableColumnHeader,
  DataTableColumnHeaderWithSummary,
} from "./column-header";
import { Checkbox } from "../ui/checkbox";
import { isMimeValue, MimeCell } from "./mime-cell";
import type { DataType } from "@/core/kernel/messages";
import { TableColumnSummary } from "./column-summary";
import type { FilterType } from "./filters";
import {
  type DataTableSelection,
  INDEX_COLUMN_NAME,
  type FieldTypesWithExternalType,
} from "./types";
import { UrlDetector } from "./url-detector";
import { cn } from "@/utils/cn";
import { uniformSample } from "./uniformSample";
import { DatePopover } from "./date-popover";
import { Objects } from "@/utils/objects";
import { Maps } from "@/utils/maps";
import { exactDateTime } from "@/utils/dates";

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
    if (typeof item !== "object") {
      return;
    }
    // We will be a bit defensive and assume values are not homogeneous.
    // If any is a mimetype, then we will treat it as a mimetype (i.e. not sortable)
    Object.entries(item as object).forEach(([key, value], idx) => {
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
  textJustifyColumns,
  wrappedColumns,
  showDataTypes,
}: {
  rowHeaders: string[];
  selection: DataTableSelection;
  fieldTypes: FieldTypesWithExternalType;
  textJustifyColumns?: Record<string, "left" | "center" | "right">;
  wrappedColumns?: string[];
  showDataTypes?: boolean;
}): Array<ColumnDef<T>> {
  const rowHeadersSet = new Set(rowHeaders);

  const typesByColumn = Maps.keyBy(fieldTypes, (entry) => entry[0]);

  const getMeta = (key: string) => {
    const types = typesByColumn.get(key)?.[1];
    const isRowHeader = rowHeadersSet.has(key);

    if (isRowHeader || !types) {
      return {
        rowHeader: isRowHeader,
      };
    }

    return {
      rowHeader: isRowHeader,
      filterType: getFilterTypeForFieldType(types[0]),
      dtype: types[1],
      dataType: types[0],
    };
  };

  const columnKeys = [
    ...rowHeaders,
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
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return (row as any)[key];
      },

      header: ({ column }) => {
        const dtype = column.columnDef.meta?.dtype;
        const headerWithType = (
          <div className="flex flex-col">
            <span className="font-bold">{key}</span>
            {showDataTypes && dtype && (
              <span className="text-xs text-muted-foreground">{dtype}</span>
            )}
          </div>
        );

        // Row headers have no summaries
        if (rowHeadersSet.has(key)) {
          return (
            <DataTableColumnHeader header={headerWithType} column={column} />
          );
        }

        return (
          <DataTableColumnHeaderWithSummary
            key={key}
            header={headerWithType}
            column={column}
            summary={<TableColumnSummary columnId={key} />}
          />
        );
      },

      cell: ({ column, renderValue, getValue, cell }) => {
        // Row headers are bold
        if (rowHeadersSet.has(key)) {
          return <b>{String(renderValue())}</b>;
        }

        const value = getValue();
        const justify = textJustifyColumns?.[key];
        const wrapped = wrappedColumns?.includes(key);

        function selectCell() {
          if (selection !== "single-cell" && selection !== "multi-cell") {
            return;
          }

          console.log("Select", value, cell);
          cell.toggleSelected();
        }

        const format = column.getColumnFormatting?.();
        if (format) {
          return (
            <div
              onClick={selectCell}
              className={getCellStyleClass(
                justify,
                wrapped,
                cell.getIsSelected(),
              )}
            >
              {column.applyColumnFormatting(value)}
            </div>
          );
        }

        if (isPrimitiveOrNullish(value)) {
          const rendered = renderValue();
          return (
            <div
              onClick={selectCell}
              className={getCellStyleClass(
                justify,
                wrapped,
                cell.getIsSelected(),
              )}
            >
              {rendered == null ? (
                ""
              ) : typeof rendered === "string" ? (
                <UrlDetector text={rendered} />
              ) : (
                String(rendered)
              )}
            </div>
          );
        }

        if (value instanceof Date) {
          // e.g. 2010-10-07 17:15:00
          const type =
            column.columnDef.meta?.dataType === "date" ? "date" : "datetime";
          return (
            <div
              onClick={selectCell}
              className={getCellStyleClass(
                justify,
                wrapped,
                cell.getIsSelected(),
              )}
            >
              <DatePopover date={value} type={type}>
                {exactDateTime(value)}
              </DatePopover>
            </div>
          );
        }

        if (isMimeValue(value)) {
          return (
            <div
              onClick={selectCell}
              className={getCellStyleClass(
                justify,
                wrapped,
                cell.getIsSelected(),
              )}
            >
              <MimeCell value={value} />
            </div>
          );
        }

        return (
          <div
            onClick={selectCell}
            className={getCellStyleClass(
              justify,
              wrapped,
              cell.getIsSelected(),
            )}
          >
            {renderAny(getValue())}
          </div>
        );
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
      id: "__select__",
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
        />
      ),
      enableSorting: false,
      enableHiding: false,
    });
  }

  return columns;
}

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
  isSelected: boolean,
): string {
  return cn(
    "cursor-pointer", // TODO: only when select cell?
    isSelected && "bg-blue-200",
    "w-full",
    "text-left",
    justify === "center" && "text-center",
    justify === "right" && "text-right",
    wrapped && "whitespace-pre-wrap min-w-[200px] break-words",
  );
}

function renderAny(value: unknown): React.ReactNode {
  if (value == null) {
    return "";
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
