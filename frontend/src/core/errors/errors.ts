/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import type { CellId } from "../cells/ids";
import type { MarimoError } from "../kernel/messages";
import { wrapInFunction } from "./utils";
import { invariant } from "@/utils/invariant";

export interface AutoFix {
  title: string;
  description: string;
  onFix: (ctx: {
    addCodeBelow: (code: string) => void;
    editor: EditorView | undefined;
    cellId: CellId;
  }) => Promise<void>;
}

export function getAutoFixes(error: MarimoError): AutoFix[] {
  if (error.type === "multiple-defs") {
    return [
      {
        title: "Wrap in a function",
        description:
          "Wrap the cell contents in a function so they are marked as definitions of the cell.",
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

    const cellCode = IMPORT_MAPPING[name];

    return [
      {
        title: `Add '${cellCode}'`,
        description: "Add a new cell for the missing import",
        onFix: async (ctx) => {
          ctx.addCodeBelow(cellCode);
        },
      },
    ];
  }

  return [];
}

const IMPORT_MAPPING: Record<string, string> = {
  // marimo
  mo: "import marimo as mo",
  // others
  alt: "import altair as alt",
  bokeh: "import bokeh",
  dask: "import dask",
  dt: "import datetime as dt",
  json: "import json",
  math: "import math",
  np: "import numpy as np",
  os: "import os",
  pd: "import pandas as pd",
  pl: "import polars as pl",
  plotly: "import plotly",
  plt: "import matplotlib.pyplot as plt",
  px: "import plotly.express as px",
  re: "import re",
  scipy: "import scipy",
  sk: "import sklearn as sk",
  sns: "import seaborn as sns",
  stats: "import scipy.stats as stats",
  sys: "import sys",
  tf: "import tensorflow as tf",
  torch: "import torch",
  xr: "import xarray as xr",
};
