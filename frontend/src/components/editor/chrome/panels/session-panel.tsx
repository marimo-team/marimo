/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { DatabaseIcon, VariableIcon } from "lucide-react";
import React, { useCallback } from "react";
import {
  connectionsAtom,
  DataSources,
} from "@/components/datasources/datasources";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { VariableTable } from "@/components/variables/variables-table";
import { useCellIds } from "@/core/cells/cells";
import { datasetTablesAtom } from "@/core/datasets/state";
import { useVariables } from "@/core/variables/state";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

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
      <AccordionItem value="datasources" className="border-b">
        <AccordionTrigger className="px-3 py-2 text-xs font-semibold uppercase tracking-wide hover:no-underline">
          <span className="flex items-center gap-2">
            <DatabaseIcon className="w-4 h-4" />
            Data sources
            {showDatasourcesBadge && (
              <Badge
                variant="secondary"
                className="ml-1 px-1.5 py-0 mb-px text-[10px]"
              >
                {datasourcesCount}
              </Badge>
            )}
          </span>
        </AccordionTrigger>
        <AccordionContent wrapperClassName="p-0">
          <DataSources />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="variables" className="border-b-0">
        <AccordionTrigger className="px-3 py-2 text-xs font-semibold uppercase tracking-wide hover:no-underline">
          <span className="flex items-center gap-2">
            <VariableIcon className="w-4 h-4" />
            Variables
          </span>
        </AccordionTrigger>
        <AccordionContent wrapperClassName="p-0">
          {Object.keys(variables).length === 0 ? (
            <div className="px-3 py-4 text-sm text-muted-foreground">
              No variables defined
            </div>
          ) : (
            <VariableTable cellIds={cellIds.inOrderIds} variables={variables} />
          )}
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
};

export default SessionPanel;
