/* Copyright 2026 Marimo. All rights reserved. */
import { useMemo, useRef } from "react";
import { Workbook } from "@fortune-sheet/react";

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

  const workbookRef = useRef<any>(null);
  const pendingCalls = useRef<Set<string>>(new Set());
  const evaluatedCache = useRef<Map<string, any>>(new Map());

  const parseFormula = (formula: string) => {
    const match = formula.match(/^=([a-zA-Z0-9_]+)\((.*)\)$/);
    if (!match) return null;
    const name = match[1];
    const argsStr = match[2];
    const args = argsStr ? argsStr.split(",").map((t) => t.trim()) : [];
    return { name, args };
  };

  const resolveCellRef = (ref: string, data: any[][]) => {
    const match = ref.match(/^([a-zA-Z]+)([0-9]+)$/);
    if (!match) {
      const num = Number(ref);
      return isNaN(num) ? ref.replace(/^["']|["']$/g, "") : num;
    }
    const colStr = match[1].toUpperCase();
    const rowNum = parseInt(match[2], 10);

    let colIdx = 0;
    for (let i = 0; i < colStr.length; i++) {
      colIdx = colIdx * 26 + (colStr.charCodeAt(i) - 64);
    }
    colIdx = colIdx - 1;

    const rowIdx = rowNum;
    const cell = data[rowIdx] ? data[rowIdx][colIdx] : null;
    return cell && cell.v !== undefined && cell.v !== null ? cell.v : null;
  };

  const evaluateCustomFormulas = async (sheetData: any[][]) => {
    if (!sheetData) return;

    for (let r = 0; r < sheetData.length; r++) {
      const row = sheetData[r];
      if (!row) continue;
      for (let c = 0; c < row.length; c++) {
        const cell = row[c];
        if (cell && cell.f && typeof cell.f === "string" && cell.f.startsWith("=")) {
          const parsed = parseFormula(cell.f);
          if (!parsed) continue;

          const { name, args } = parsed;
          if (customFunctions.map((f) => f.toLowerCase()).includes(name.toLowerCase())) {
            const resolvedArgs = args.map((arg) => resolveCellRef(arg, sheetData));
            const callKey = `${r}-${c}-${JSON.stringify(resolvedArgs)}`;

            if (pendingCalls.current.has(callKey)) continue;
            const lastVal = evaluatedCache.current.get(callKey);
            if (lastVal !== undefined && cell.v === lastVal) {
              continue;
            }

            pendingCalls.current.add(callKey);
            try {
              const result = await run_custom_function({ name, args: resolvedArgs });
              evaluatedCache.current.set(callKey, result);
              if (cell.v !== result) {
                workbookRef.current?.setCellValue(r, c, result);
              }
            } catch (err) {
              console.error(`Failed to execute custom function ${name}:`, err);
            } finally {
              pendingCalls.current.delete(callKey);
            }
          }
        }
      }
    }
  };

  const handleChange = (sheets: any[]) => {
    const sheet = sheets[0];
    if (!sheet || !sheet.data) {return;}

    // Evaluate custom formula cells
    evaluateCustomFormulas(sheet.data);

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
