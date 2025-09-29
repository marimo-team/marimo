/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { invariant } from "@/utils/invariant";
import type { CellId } from "../cells/ids";
import type { MarimoError } from "../kernel/messages";
import { wrapInFunction } from "./utils";

export interface AutoFix {
  title: string;
  description: string;
  onFix: (ctx: {
    addCodeBelow: (code: string) => void;
    editor: EditorView | undefined;
    cellId: CellId;
    setAiCompletionCell?: (cell: {
      cellId: CellId;
      initialPrompt?: string;
    }) => void;
  }) => Promise<void>;
}

export function getAutoFixes(
  error: MarimoError,
  opts: {
    aiEnabled: boolean;
  },
): AutoFix[] {
  if (error.type === "multiple-defs") {
    return [
      {
        title: "Fix: Wrap in a function",
        description:
          "Make this cell's variables local by wrapping the cell in a function.",
        onFix: async (ctx) => {
          invariant(ctx.editor, "Editor is null");
          const code = wrapInFunction(ctx.editor.state.doc.toString());
          ctx.editor.dispatch({
            changes: {
              from: 0,
              to: ctx.editor.state.doc.length,
              insert: code,
            },
          });
        },
      },
    ];
  }

  if (error.type === "exception" && error.exception_type === "NameError") {
    const name = error.msg.match(/name '(.+)' is not defined/)?.[1];

    if (!name || !(name in IMPORT_MAPPING)) {
      return [];
    }

    const cellCode = getImportCode(name);

    return [
      {
        title: `Fix: Add '${cellCode}'`,
        description: "Add a new cell for the missing import",
        onFix: async (ctx) => {
          ctx.addCodeBelow(cellCode);
        },
      },
    ];
  }

  if (error.type === "sql-error") {
    // Only show AI fix if AI is enabled
    if (!opts.aiEnabled) {
      return [];
    }
    return [
      {
        title: "Fix with AI",
        description: "Fix the SQL statement",
        onFix: async (ctx) => {
          ctx.setAiCompletionCell?.({
            cellId: ctx.cellId,
            initialPrompt: `Fix the SQL statement: ${error.msg}`,
          });
        },
      },
    ];
  }

  return [];
}

export function getImportCode(name: string): string {
  const moduleName = IMPORT_MAPPING[name];
  return moduleName === name
    ? `import ${moduleName}`
    : `import ${moduleName} as ${name}`;
}

const IMPORT_MAPPING: Record<string, string> = {
  // libraries
  mo: "marimo",
  alt: "altair",
  bokeh: "bokeh",
  dask: "dask",
  np: "numpy",
  pd: "pandas",
  pl: "polars",
  plotly: "plotly",
  plt: "matplotlib.pyplot",
  px: "plotly.express",
  scipy: "scipy",
  sk: "sklearn",
  sns: "seaborn",
  stats: "scipy.stats",
  tf: "tensorflow",
  torch: "torch",
  xr: "xarray",
  // built-ins
  dt: "datetime",
  json: "json",
  math: "math",
  os: "os",
  re: "re",
  sys: "sys",
};
