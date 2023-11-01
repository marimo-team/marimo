/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { useCellErrors } from "../../../core/state/cells";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";
import { CellLinkError } from "@/editor/links/cell-link";
import { PartyPopperIcon } from "lucide-react";

export const ErrorsPanel: React.FC = () => {
  const errors = useCellErrors();

  if (errors.length === 0) {
    return (
      <div className="mx-6 my-6 flex flex-row gap-2 items-center rounded-lg">
        <PartyPopperIcon className="text-accent-foreground" />
        <span className="mt-[0.25rem] text-accent-foreground">
          {" "}
          No errors!{" "}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col overflow-auto">
      {errors.map((error) => (
        <div key={error.cellId}>
          <div className="text-xs font-mono font-semibold bg-muted border-y px-2 py-1">
            <CellLinkError cellId={error.cellId} />
          </div>
          <div key={error.cellId} className="px-2">
            <MarimoErrorOutput key={error.cellId} errors={error.output.data} />
          </div>
        </div>
      ))}
    </div>
  );
};
