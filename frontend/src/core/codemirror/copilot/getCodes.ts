/* Copyright 2024 Marimo. All rights reserved. */
import { getAllEditorViews } from "@/core/cells/cells";
import { getEditorCodeAsPython } from "../language/utils";

export function getCodes(otherCode: string) {
  // Get all other cells' code
  // Put `import` statements at the top, as it can help copilot give better suggestions
  // TODO: we should sort this topologically
  const codes = getAllEditorViews()
    .map((editorView) => {
      const code = getEditorCodeAsPython(editorView);
      if (code === otherCode) {
        return null;
      }
      return code;
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
