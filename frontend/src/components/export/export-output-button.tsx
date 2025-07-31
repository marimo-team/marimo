/* Copyright 2024 Marimo. All rights reserved. */

import { type CellId, CellOutputId } from "@/core/cells/ids";
import { downloadHTMLAsImage } from "@/utils/download";

export function downloadCellOutput(cellId: CellId) {
  const output = document.getElementById(CellOutputId.create(cellId));
  if (output) {
    output.classList.add("printing-output");
    downloadHTMLAsImage(output, "result.png").finally(() => {
      output.classList.remove("printing-output");
    });
  }
}
