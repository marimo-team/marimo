/* Copyright 2023 Marimo. All rights reserved. */
import { downloadHTMLAsImage } from "@/utils/download";
import { CellId } from "@/core/cells/ids";

export function downloadCellOutput(cellId: CellId) {
  const output = document.getElementById(`output-${cellId}`);
  if (output) {
    output.classList.add("printing-output");
    downloadHTMLAsImage(output, "result.png").finally(() => {
      output.classList.remove("printing-output");
    });
  }
}
