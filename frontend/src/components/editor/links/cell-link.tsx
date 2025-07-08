/* Copyright 2024 Marimo. All rights reserved. */

import type { JSX } from "react"; /* Copyright 2024 Marimo. All rights reserved. */
import {
  SCRATCH_CELL_ID,
  useCellActions,
  useCellIds,
  useCellNames,
} from "@/core/cells/cells";
import { type CellId, HTMLCellId } from "@/core/cells/ids";
import { displayCellName } from "@/core/cells/names";
import { goToCellLine } from "@/core/codemirror/go-to-definition/utils";
import { useFilename } from "@/core/saving/filename";
import { cn } from "@/utils/cn";
import { Logger } from "../../../utils/Logger";

interface Props {
  cellId: CellId;
  className?: string;
  shouldScroll?: boolean;
  skipScroll?: boolean;
  onClick?: () => void;
  formatCellName?: (name: string) => string;
  variant?: "destructive" | "focus";
}

/* Component that adds a link to a cell, with styling. */
export const CellLink = (props: Props): JSX.Element => {
  const { className, cellId, variant, onClick, formatCellName, skipScroll } =
    props;
  const cellName = useCellNames()[cellId] ?? "";
  const cellIndex = useCellIds().inOrderIds.indexOf(cellId);
  const { showCellIfHidden } = useCellActions();
  const formatName = formatCellName ?? ((name: string) => name);

  return (
    <div
      className={cn(
        "inline-block cursor-pointer text-link hover:underline",
        className,
      )}
      role="link"
      tabIndex={-1}
      onClick={(e) => {
        // Scratch causes a crash since scratch is not registered like a
        // normal cell.
        if (cellId === SCRATCH_CELL_ID) {
          return false;
        }
        showCellIfHidden({ cellId });
        e.stopPropagation();
        e.preventDefault();
        requestAnimationFrame(() => {
          const succeeded = scrollAndHighlightCell(cellId, variant, skipScroll);
          if (succeeded) {
            onClick?.();
          }
        });
      }}
    >
      {formatName(displayCellName(cellName, cellIndex))}
    </div>
  );
};

/* Component that adds a link to a cell, for use in a MarimoError. */
export const CellLinkError = (
  props: Pick<Props, "className" | "cellId">,
): JSX.Element => {
  return <CellLink {...props} variant={"destructive"} />;
};

/* Component that adds a link to a cell, for use in tracebacks. */
export const CellLinkTraceback = ({
  cellId,
  lineNumber,
}: {
  cellId: CellId;
  lineNumber: number;
}): JSX.Element => {
  const filename = useFilename();
  return (
    <CellLink
      cellId={cellId}
      onClick={() => goToCellLine(cellId, lineNumber)}
      skipScroll={true}
      variant={"destructive"}
      className="traceback-cell-link"
      formatCellName={(name: string) =>
        cellId === SCRATCH_CELL_ID
          ? "scratch"
          : `marimo://${filename || "untitled"}#cell=${name}`
      }
    />
  );
};

export function scrollAndHighlightCell(
  cellId: CellId,
  variant?: "destructive" | "focus",
  skipScroll?: boolean,
): boolean {
  const cellHtmlId = HTMLCellId.create(cellId);
  const cell: HTMLElement | null = document.getElementById(cellHtmlId);

  if (cell === null) {
    Logger.error(`Cell ${cellHtmlId} not found on page.`);
    return false;
  }
  if (!skipScroll) {
    cell.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  if (variant === "destructive") {
    cell.classList.add("error-outline");
    setTimeout(() => {
      cell.classList.remove("error-outline");
    }, 2000);
  }
  if (variant === "focus") {
    cell.classList.add("focus-outline");
    setTimeout(() => {
      cell.classList.remove("focus-outline");
    }, 2000);
  }

  return true;
}
