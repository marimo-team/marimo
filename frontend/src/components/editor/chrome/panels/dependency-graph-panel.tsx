/* Copyright 2024 Marimo. All rights reserved. */

import type React from "react";
import { useCellDataAtoms, useCellIds } from "@/core/cells/cells";
import { useVariables } from "@/core/variables/state";
import { cn } from "@/utils/cn";
import { DependencyGraph } from "../../../dependency-graph/dependency-graph";

export const DependencyGraphPanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();
  const [cells] = useCellDataAtoms();

  return (
    <div className={cn("w-full h-full flex-1 mx-auto -mb-4 relative")}>
      <DependencyGraph
        cellAtoms={cells}
        variables={variables}
        cellIds={cellIds.inOrderIds}
      />
    </div>
  );
};
