/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { cellErrors } from "../../../core/state/cells";
import { MarimoErrorOutput } from "../../output/MarimoErrorOutput";
import { CellLinkError } from "@/editor/links/cell-link";
import { useAtomValue } from "jotai";
import { PartyPopperIcon } from "lucide-react";

export const ErrorsPanel: React.FC = () => {
  const errors = useAtomValue(cellErrors);

  if (errors.length === 0) {
    return (
      <div className="mx-6 my-6 py-4 px-4 flex flex-row gap-2 items-center bg-accent rounded-lg">
        <PartyPopperIcon className="text-accent-foreground" />
        <span className="mt-[0.25rem] text-accent-foreground font-semibold">
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
