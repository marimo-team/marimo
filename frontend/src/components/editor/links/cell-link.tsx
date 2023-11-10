/* Copyright 2023 Marimo. All rights reserved. */
import { CellId, HTMLCellId } from "@/core/cells/ids";
import { Logger } from "../../../utils/Logger";
import { cn } from "@/utils/cn";

interface Props {
  cellId: CellId;
  className?: string;
  variant?: "destructive" | "focus";
}

/* Component that adds a link to a cell, with styling. */
export const CellLink = (props: Props): JSX.Element => {
  const { className, cellId, variant } = props;
  const cellName = HTMLCellId.create(cellId);

  return (
    <div
      className={cn(
        "inline-block cursor-pointer text-[var(--blue-10)] hover:underline",
        className
      )}
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();

        const cell: HTMLElement | null = document.getElementById(cellName);

        if (cell === null) {
          Logger.error(`Cell ${cellName} not found on page.`);
        } else {
          cell.scrollIntoView({ behavior: "smooth", block: "center" });

          if (variant === "destructive") {
            cell.classList.add("error-outline");
            setTimeout(() => {
              cell.classList.remove("error-outline");
            }, 1500);
          }
          if (variant === "focus") {
            cell.classList.add("focus-outline");
            setTimeout(() => {
              cell.classList.remove("focus-outline");
            }, 1500);
          }
        }
      }}
    >
      {cellName}
    </div>
  );
};

/* Component that adds a link to a cell, for use in a MarimoError. */
export const CellLinkError = (
  props: Pick<Props, "className" | "cellId">
): JSX.Element => {
  const { className, cellId } = props;
  return (
    <CellLink className={className} cellId={cellId} variant={"destructive"} />
  );
};
