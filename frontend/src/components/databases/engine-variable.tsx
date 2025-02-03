/* Copyright 2024 Marimo. All rights reserved. */
import { getCellEditorView } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { goToVariableDefinition } from "@/core/codemirror/go-to-definition/commands";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import { cn } from "@/utils/cn";

interface Props {
  variableName: VariableName;
  className?: string;
}

export const EngineVariable: React.FC<Props> = ({
  variableName,
  className,
}) => {
  const onClick = () => {
    const cellId = findCellId(variableName);
    if (!cellId) {
      return;
    }
    const editorView = getCellEditorView(cellId);
    if (editorView) {
      goToVariableDefinition(editorView, variableName);
    }
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "text-link opacity-80 hover:opacity-100 hover:underline",
        className,
      )}
    >
      {variableName}
    </button>
  );
};

function findCellId(variableName: VariableName): CellId | undefined {
  const variables = store.get(variablesAtom);
  const variable = variables[variableName];
  if (!variable) {
    return undefined;
  }
  return variable.declaredBy[0];
}
