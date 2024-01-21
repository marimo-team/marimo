/* Copyright 2024 Marimo. All rights reserved. */
import { useCellDataAtoms, useCellIds } from "@/core/cells/cells";
import { useVariables } from "@/core/variables/state";
import React from "react";
import { DependencyGraph } from "../../../dependency-graph/dependency-graph";
import { cn } from "@/utils/cn";

export const DependencyGraphPanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();
  const [cells] = useCellDataAtoms();

  return (
    <div className={cn("w-full h-full flex-1 mx-auto -mb-4 relative")}>
      <DependencyGraph
        cellAtoms={cells}
        variables={variables}
        cellIds={cellIds}
      />
    </div>
  );
};
