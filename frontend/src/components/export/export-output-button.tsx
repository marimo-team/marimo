/* Copyright 2024 Marimo. All rights reserved. */
import { downloadHTMLAsImage } from "@/utils/download";
import { CellOutputId, type CellId } from "@/core/cells/ids";

export function downloadCellOutput(cellId: CellId) {
  const output = document.getElementById(CellOutputId.create(cellId));
  if (output) {
    output.classList.add("printing-output");
    downloadHTMLAsImage(output, "result.png").finally(() => {
      output.classList.remove("printing-output");
    });
  }
}
