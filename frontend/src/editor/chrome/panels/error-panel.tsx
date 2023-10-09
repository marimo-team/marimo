/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { cellErrors } from "../../../core/state/cells";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";
import { useAtomValue } from "jotai";

export const ErrorsPanel: React.FC = () => {
  const errors = useAtomValue(cellErrors);

  if (errors.length === 0) {
    // TODO: show an empty state
    return null;
  }

  return (
    <div className="flex flex-col overflow-auto">
      {errors.map((error) => (
        <div key={error.cellId}>
          <div className="text-sm font-semibold bg-muted border-y px-2 py-1">
            Cell {error.cellId}
          </div>
          <div key={error.cellId} className="px-2">
            <MarimoErrorOutput key={error.cellId} errors={error.output.data} />
          </div>
        </div>
      ))}
    </div>
  );
};
