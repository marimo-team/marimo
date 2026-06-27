/* Copyright 2026 Marimo. All rights reserved. */
import { useMemo, useRef, useState, useEffect } from "react";
import { Workbook } from "@fortune-sheet/react";
import { Parser } from "@fortune-sheet/formula-parser";

// Cache for evaluated results
const formulaCache = new Map<string, any>();
const pendingCalls = new Set<string>();

// Global ref to keep track of the current RPC runner
let runCustomFunctionRPC: ((req: { name: string; args: any[] }) => Promise<any>) | null = null;
let triggerRerender: (() => void) | null = null;

// Wrap Parser.prototype.parse to inject our custom functions
const originalParse = Parser.prototype.parse;
if (originalParse) {
  Parser.prototype.parse = function (expression: any, context: any) {
    if (!this.functions) {
      (this as any).functions = Object.create(null);
    }
    // Get the registered custom function names
    const customFuncNames = (window as any).__marimoCustomFunctions || [];
    customFuncNames.forEach((name: string) => {
      const upperName = name.toUpperCase();
      this.functions[upperName] = (...params: any[]) => {
        // Flatten params to get raw values
        const args = params.map((p) =>
          p && typeof p === "object" && "value" in p ? p.value : p
        );

        const cacheKey = `${upperName}-${JSON.stringify(args)}`;

        if (formulaCache.has(cacheKey)) {
          return formulaCache.get(cacheKey);
        }

        // Trigger async Python evaluation if not pending
        if (!pendingCalls.has(cacheKey) && runCustomFunctionRPC) {
          pendingCalls.add(cacheKey);
          runCustomFunctionRPC({ name, args })
            .then((result) => {
              formulaCache.set(cacheKey, result);
              pendingCalls.delete(cacheKey);
              // Trigger a re-evaluation in FortuneSheet
              if (triggerRerender) {
                triggerRerender();
              }
            })
            .catch((err) => {
              console.error("Failed to run custom function:", err);
              pendingCalls.delete(cacheKey);
            });
        }

        // Return a temporary loading string
        return "...";
      };
    });

    return originalParse.call(this, expression, context);
  };
}

interface Props {
  initialData: Record<string, any>[];
  columnNames: string[];
  customFunctions: string[];
  run_custom_function: (req: { name: string; args: any[] }) => Promise<any>;
  onChange: (data: Record<string, any>[]) => void;
}

export default function WorkbookWrapper({
  initialData,
  columnNames,
  customFunctions,
  run_custom_function,
  onChange,
}: Props) {
  const workbookRef = useRef<any>(null);
  const [, setTick] = useState(0);

  // Bind the callback references to window/globals on render
  (window as any).__marimoCustomFunctions = customFunctions;
  runCustomFunctionRPC = run_custom_function;
  triggerRerender = () => {
    if (workbookRef.current) {
      const val = workbookRef.current.getCellValue(0, 0);
      workbookRef.current.setCellValue(0, 0, val);
    }
    setTick((t) => t + 1);
  };

  useEffect(() => {
    return () => {
      formulaCache.clear();
      pendingCalls.clear();
      runCustomFunctionRPC = null;
      triggerRerender = null;
    };
  }, []);

  const sheetData = useMemo(() => {
    const celldata: any[] = [];

    // Populate header row (Row 0)
    columnNames.forEach((col, c) => {
      celldata.push({
        r: 0,
        c: c,
        v: {
          v: col,
          m: col,
          bl: 1, // bold
          bg: "#f3f4f6", // gray-100
          fc: "#1f2937", // gray-800
          ht: 1, // center
          vt: 1, // center
          ct: { fa: "General", t: "s" },
        },
      });
    });

    // Populate data rows (Row 1 onwards)
    initialData.forEach((rowObj, r) => {
      columnNames.forEach((col, c) => {
        const val = rowObj[col];
        if (val !== null && val !== undefined) {
          let t: "s" | "n" | "b" = "s";
          if (typeof val === "number") {
            t = "n";
          } else if (typeof val === "boolean") {
            t = "b";
          }
          celldata.push({
            r: r + 1,
            c: c,
            v: {
              v: val,
              m: String(val),
              ct: { fa: "General", t },
            },
          });
        }
      });
    });

    return [
      {
        name: "Sheet1",
        color: "",
        id: "sheet_1",
        status: 1,
        order: 0,
        row: Math.max(100, initialData.length + 15),
        column: Math.max(26, columnNames.length + 5),
        celldata: celldata,
        config: {
          frozen: {
            type: "row",
            range: {
              row_focus: 1,
              column_focus: 0,
            },
          },
        },
      },
    ] as any;
  }, [initialData, columnNames]);

  const handleChange = (sheets: any[]) => {
    const sheet = sheets[0];
    if (!sheet || !sheet.data) {return;}

    const headerRow = sheet.data[0];
    if (!headerRow) {return;}

    const currentColumns: string[] = [];
    headerRow.forEach((cell: any, c: number) => {
      const colName =
        cell && cell.v !== undefined && cell.v !== null
          ? String(cell.v).trim()
          : "";
      if (colName) {
        currentColumns.push(colName);
      }
    });

    if (currentColumns.length === 0) {return;}

    // Find the last row with any non-empty cell
    let lastNonEmptyRowIdx = 0;
    for (let r = 1; r < sheet.data.length; r++) {
      const row = sheet.data[r];
      if (
        row &&
        row.some(
          (cell: any) =>
            cell !== null &&
            cell !== undefined &&
            cell.v !== null &&
            cell.v !== undefined &&
            cell.v !== "",
        )
      ) {
        lastNonEmptyRowIdx = r;
      }
    }

    const updatedData: Record<string, any>[] = [];
    for (let r = 1; r <= lastNonEmptyRowIdx; r++) {
      const row = sheet.data[r];
      const rowObj: Record<string, any> = {};
      currentColumns.forEach((col, c) => {
        const cell = row ? row[c] : null;
        rowObj[col] =
          cell && cell.v !== undefined && cell.v !== null ? cell.v : null;
      });
      updatedData.push(rowObj);
    }

    onChange(updatedData);
  };

  return (
    <div className="w-full h-[500px] border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden relative">
      <Workbook ref={workbookRef} data={sheetData} onChange={handleChange} />
    </div>
  );
}
