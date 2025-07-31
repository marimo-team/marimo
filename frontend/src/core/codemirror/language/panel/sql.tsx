/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { AlertCircle, CircleHelpIcon } from "lucide-react";
import { transformDisplayName } from "@/components/databases/display";
import { DatabaseLogo } from "@/components/databases/icon";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  dataConnectionsMapAtom,
  setLatestEngineSelected,
} from "@/core/datasets/data-source-connections";
import {
  type ConnectionName,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/engines";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { useNonce } from "@/hooks/useNonce";

interface SelectProps {
  selectedEngine: ConnectionName;
  onChange: (engine: ConnectionName) => void;
}

export const SQLEngineSelect: React.FC<SelectProps> = ({
  selectedEngine,
  onChange,
}) => {
  const connectionsMap = useAtomValue(dataConnectionsMapAtom);

  const internalEngineConnections: DataSourceConnection[] = [];
  const userDefinedConnections: DataSourceConnection[] = [];
  for (const [connName, connection] of connectionsMap.entries()) {
    INTERNAL_SQL_ENGINES.has(connName)
      ? internalEngineConnections.push(connection)
      : userDefinedConnections.push(connection);
  }

  // Use nonce to force re-render as languageAdapter.engine may not trigger change
  // If it's disconnected, we display the engine variable.
  const rerender = useNonce();

  const engineIsDisconnected =
    selectedEngine && !connectionsMap.has(selectedEngine);

  const handleSelectEngine = (value: string) => {
    if (value === HELP_KEY) {
      window.open(HELP_URL, "_blank");
      return;
    }

    const nextEngine = connectionsMap.get(value as ConnectionName);
    if (nextEngine) {
      rerender();
      onChange(nextEngine.name);
      // Update the latest engine selected
      setLatestEngineSelected(nextEngine.name);
    }
  };

  const renderConnections = (connections: DataSourceConnection[]) => {
    // HACK: Ignore iceberg connections
    // Ideally source_type should be on the DataSourceConnection object
    connections = connections.filter(
      (connection) => connection.source !== "iceberg",
    );

    return connections.map((connection) => (
      <SelectItem key={connection.name} value={connection.name}>
        <div className="flex items-center gap-1">
          <DatabaseLogo className="h-3 w-3" name={connection.dialect} />
          <span className="truncate">
            {transformDisplayName(connection.display_name)}
          </span>
        </div>
      </SelectItem>
    ));
  };

  return (
    <div className="flex flex-row gap-1 items-center">
      <Select value={selectedEngine} onValueChange={handleSelectEngine}>
        <SelectTrigger className="text-xs border-border !shadow-none !ring-0 h-4.5 px-1.5">
          <SelectValue placeholder="Select an engine" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Database connections</SelectLabel>
            {engineIsDisconnected && (
              <SelectItem key={selectedEngine} value={selectedEngine}>
                <div className="flex items-center gap-1 opacity-50">
                  <AlertCircle className="h-3 w-3" />
                  <span className="truncate">
                    {transformDisplayName(selectedEngine)}
                  </span>
                </div>
              </SelectItem>
            )}
            {/* Prioritize showing user-defined connections */}
            {renderConnections(userDefinedConnections)}
            {userDefinedConnections.length > 0 && <SelectSeparator />}
            {renderConnections(internalEngineConnections)}
            <SelectSeparator />
            <SelectItem className="text-muted-foreground" value={HELP_KEY}>
              <a
                className="flex items-center gap-1"
                href={HELP_URL}
                target="_blank"
                rel="noreferrer"
              >
                <CircleHelpIcon className="h-3 w-3" />
                <span>How to add a database connection</span>
              </a>
            </SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};

const HELP_KEY = "__help__";
const HELP_URL =
  "http://docs.marimo.io/guides/working_with_data/sql/#connecting-to-a-custom-database";
