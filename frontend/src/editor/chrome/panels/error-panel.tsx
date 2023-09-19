/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { useCells } from "../../../core/state/cells";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";

export const ErrorsPanel: React.FC = (props) => {
  const cells = useCells();
  const errors = cells.present
    .map((cell) =>
      cell.output?.mimetype === "application/vnd.marimo+error"
        ? {
            output: cell.output,
            cellId: cell.key,
          }
        : null
    )
    .filter(Boolean);
  return (
    <div className="flex flex-col gap-3 px-2">
      {errors.map((error) => (
        <div key={error.cellId}>
          <MarimoErrorOutput key={error.cellId} errors={error.output.data} />
        </div>
      ))}
    </div>
  );
};
