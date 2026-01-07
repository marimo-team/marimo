/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";
import { useCellDataAtoms, useCellIds } from "@/core/cells/cells";
import { useVariables } from "@/core/variables/state";
import { cn } from "@/utils/cn";
import { DependencyGraph } from "../../../dependency-graph/dependency-graph";
import { MinimapContent } from "../../../dependency-graph/minimap-content";
import { useDependencyPanelTab } from "../wrapper/useDependencyPanelTab";

const DependencyGraphPanel: React.FC = () => {
  const { dependencyPanelTab } = useDependencyPanelTab();
  const variables = useVariables();
  const cellIds = useCellIds();
  const [cells] = useCellDataAtoms();

  return (
    <div className={cn("w-full h-full flex-1 mx-auto -mb-4 relative")}>
      {dependencyPanelTab === "minimap" ? (
        <MinimapContent />
      ) : (
        <DependencyGraph
          cellAtoms={cells}
          variables={variables}
          cellIds={cellIds.inOrderIds}
        />
      )}
    </div>
  );
};

export default DependencyGraphPanel;
