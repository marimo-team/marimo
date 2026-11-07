/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { BugIcon } from "lucide-react";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Button } from "@/components/ui/button";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { displayCellName } from "@/core/cells/names";
import type { CellErrorEntry } from "@/core/errors/error-entries";
import type { MarimoError } from "@/core/kernel/messages";
import { viewStateAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import { FeedbackModal } from "../chrome/components/feedback-button";

export function ReportMarimoBugButton({
  cellId,
  errors,
  code,
}: {
  cellId: CellId;
  errors: MarimoError[];
  code?: string;
}) {
  const { openModal } = useImperativeModal();
  const view = useAtomValue(viewStateAtom);
  const internalErrors = errors.filter(
    (error) => error.type === "exception" && error.is_internal === true,
  );

  if (view.mode !== "edit" || internalErrors.length === 0) {
    return null;
  }

  const report = () => {
    const notebook = store.get(notebookAtom);
    const cell = notebook.cellData[cellId];
    const evidence: CellErrorEntry = {
      cellId,
      cellName: cell
        ? displayCellName(cell.name, notebook.cellIds.indexOf(cellId))
        : "Cell",
      cellCode: code ?? "",
      errorData: internalErrors,
    };
    openModal(<FeedbackModal initialErrors={[structuredClone(evidence)]} />);
  };

  return (
    <Button size="xs" variant="outline" onClick={report}>
      <BugIcon className="h-3 w-3 mr-2" />
      Report a marimo bug
    </Button>
  );
}
