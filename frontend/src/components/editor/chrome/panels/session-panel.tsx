/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { DatabaseIcon, VariableIcon } from "lucide-react";
import React, { useCallback } from "react";
import {
  connectionsAtom,
  DataSources,
} from "@/components/datasources/datasources";
import { Accordion } from "@/components/ui/accordion";
import { VariableTable } from "@/components/variables/variables-table";
import { useCellIds } from "@/core/cells/cells";
import { datasetTablesAtom } from "@/core/datasets/state";
import { useVariables } from "@/core/variables/state";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import {
  PanelAccordionContent,
  PanelAccordionItem,
  PanelAccordionTrigger,
  PanelBadge,
} from "./components";

type OpenSections = "variables" | "datasources";

interface SessionPanelState {
  openSections: OpenSections[];
  hasUserInteracted: boolean;
}

const sessionPanelAtom = atomWithStorage<SessionPanelState>(
  "marimo:session-panel:state",
  { openSections: ["variables"], hasUserInteracted: false },
  jotaiJsonStorage,
);

const SessionPanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();
  const tables = useAtomValue(datasetTablesAtom);
  const dataConnections = useAtomValue(connectionsAtom);
  const [state, setState] = useAtom(sessionPanelAtom);

  const datasourcesCount = tables.length + dataConnections.length;

  // If the user hasn't interacted with the accordion and there are connections, show datasources open
  const openSections =
    !state.hasUserInteracted && datasourcesCount > 0
      ? [...new Set([...state.openSections, "datasources"])]
      : state.openSections;

  const handleValueChange = useCallback(
    (value: OpenSections[]) => {
      setState({
        openSections: value,
        hasUserInteracted: true,
      });
    },
    [setState],
  );

  const isDatasourcesOpen = openSections.includes("datasources");
  const showDatasourcesBadge = !isDatasourcesOpen && datasourcesCount > 0;

  return (
    <Accordion
      type="multiple"
      value={openSections}
      onValueChange={handleValueChange}
      className="flex flex-col h-full overflow-auto"
    >
      <PanelAccordionItem value="datasources">
        <PanelAccordionTrigger>
          <DatabaseIcon className="w-4 h-4" />
          Data sources
          {showDatasourcesBadge && <PanelBadge>{datasourcesCount}</PanelBadge>}
        </PanelAccordionTrigger>
        <PanelAccordionContent>
          <DataSources />
        </PanelAccordionContent>
      </PanelAccordionItem>

      <PanelAccordionItem value="variables" lastItem={true}>
        <PanelAccordionTrigger>
          <VariableIcon className="w-4 h-4" />
          Variables
        </PanelAccordionTrigger>
        <PanelAccordionContent>
          {Object.keys(variables).length === 0 ? (
            <div className="px-3 py-4 text-sm text-muted-foreground">
              No variables defined
            </div>
          ) : (
            <VariableTable cellIds={cellIds.inOrderIds} variables={variables} />
          )}
        </PanelAccordionContent>
      </PanelAccordionItem>
    </Accordion>
  );
};

export default SessionPanel;
