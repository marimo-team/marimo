/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { DatabaseIcon, VariableIcon } from "lucide-react";
import React from "react";
import { DataSources } from "@/components/datasources/datasources";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { VariableTable } from "@/components/variables/variables-table";
import { useCellIds } from "@/core/cells/cells";
import { useDatasets } from "@/core/datasets/state";
import { useVariables } from "@/core/variables/state";
import { jotaiJsonStorage } from "@/utils/storage/jotai";

const openSectionsAtom = atomWithStorage<string[]>(
  "marimo:session-panel:open-sections",
  ["variables"],
  jotaiJsonStorage,
);

const SessionPanel: React.FC = () => {
  const variables = useVariables();
  const cellIds = useCellIds();
  const datasets = useDatasets();
  const [openSections, setOpenSections] = useAtom(openSectionsAtom);

  const datasourcesCount = datasets.tables.length;
  const isDatasourcesOpen = openSections.includes("datasources");

  return (
    <Accordion
      type="multiple"
      value={openSections}
      onValueChange={setOpenSections}
      className="flex flex-col h-full overflow-auto"
    >
      <AccordionItem value="datasources" className="border-b">
        <AccordionTrigger className="px-3 py-2 text-xs font-semibold uppercase tracking-wide hover:no-underline">
          <span className="flex items-center gap-2">
            <DatabaseIcon className="w-4 h-4" />
            Data sources
            {!isDatasourcesOpen && datasourcesCount > 0 && (
              <Badge
                variant="secondary"
                className="ml-1 px-1.5 py-0 text-[10px]"
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
