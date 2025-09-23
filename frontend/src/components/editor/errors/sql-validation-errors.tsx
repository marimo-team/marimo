/* Copyright 2024 Marimo. All rights reserved. */

import { AlertCircleIcon } from "lucide-react";
import type { CellId } from "@/core/cells/ids";
import { useSqlValidationErrorsForCell } from "@/core/codemirror/language/languages/sql/validation-errors";

export const SqlValidationErrorBanner = ({ cellId }: { cellId: CellId }) => {
  const error = useSqlValidationErrorsForCell(cellId);

  if (!error) {
    return;
  }

  return (
    <div className="p-3 text-sm flex flex-col text-muted-foreground gap-1.5 bg-destructive/5">
      <div className="flex items-start gap-1.5">
        <AlertCircleIcon size={13} className="mt-[3px] text-destructive" />
        <p>
          <span className="font-bold text-destructive">{error.errorType}:</span>{" "}
          {error.errorMessage}
        </p>
      </div>

      {error.codeblock && (
        <pre
          lang="sql"
          className="text-xs bg-muted rounded p-2 pb-0 mx-3 overflow-x-auto font-mono whitespace-pre-wrap"
        >
          {error.codeblock}
        </pre>
      )}
    </div>
  );
};
