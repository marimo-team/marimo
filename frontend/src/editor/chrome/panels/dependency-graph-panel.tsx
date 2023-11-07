/* Copyright 2023 Marimo. All rights reserved. */
import { useCellDataAtoms, useCellIds } from "@/core/state/cells";
import { useVariables } from "@/core/variables/state";
import React from "react";
import { DependencyGraph } from "../../../components/dependency-graph/dependency-graph";

export const DependencyGraphPanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();
  const [cells] = useCellDataAtoms();

  return (
    <div className="w-[300px] flex-1 mx-auto">
      <DependencyGraph
        cellAtoms={cells}
        variables={variables}
        cellIds={cellIds}
      />
    </div>
  );
};
