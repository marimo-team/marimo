/* Copyright 2023 Marimo. All rights reserved. */
import { getCells } from "@/core/state/cells";

export function getCodes(otherCode: string) {
  // Get all other cells' code
  // Put `import` statements at the top, as it can help copilot give better suggestions
  // TODO: we should sort this topologically
  const codes = getCells()
    .map((cell) => {
      if (cell.ref.current?.editorView.state.doc.toString() === otherCode) {
        return null;
      }
      return cell.ref.current?.editorView.state.doc.toString();
    })
    .filter(Boolean)
    .sort((a, b) => {
      if (a.startsWith("import") && !b.startsWith("import")) {
        return -1;
      }
      if (!a.startsWith("import") && b.startsWith("import")) {
        return 1;
      }
      return 0;
    });

  return [...codes, otherCode].join("\n");
}
