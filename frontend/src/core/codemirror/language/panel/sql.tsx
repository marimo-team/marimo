/* Copyright 2026 Marimo. All rights reserved. */

import type { SelectTriggerProps } from "@radix-ui/react-select";
import { useAtomValue } from "jotai";
import {
  AlertCircle,
  CircleHelpIcon,
  DatabaseZap,
  SearchCheck,
} from "lucide-react";
import { getCellForDomProps } from "@/components/data-table/cell-utils";
import { transformDisplayName } from "@/components/databases/display";
import { DatabaseLogo } from "@/components/databases/icon";
import { Button } from "@/components/ui/button";
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
import { Tooltip } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
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
import { clearAllSqlValidationErrors } from "../languages/sql/banner-validation-errors";
import { type SQLMode, useSQLMode } from "../languages/sql/sql-mode";

interface SelectProps {
  selectedEngine: ConnectionName;
  onChange: (engine: ConnectionName) => void;
  cellId: CellId;
}

export const SQLEngineSelect: React.FC<SelectProps> = ({
  selectedEngine,
  onChange,
  cellId,
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
          <span className="truncate ml-0.5">
            {transformDisplayName(connection.display_name)}
          </span>
        </div>
      </SelectItem>
    ));
  };

  return (
    <div className="flex flex-row gap-1 items-center">
      <Select value={selectedEngine} onValueChange={handleSelectEngine}>
        <SQLSelectTrigger {...getCellForDomProps(cellId)}>
          <SelectValue placeholder="Select an engine" />
        </SQLSelectTrigger>
        <SelectContent {...getCellForDomProps(cellId)}>
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

export const SQLModeSelect: React.FC = () => {
  const { sqlMode, setSQLMode } = useSQLMode();

  const handleToggleMode = () => {
    const nextMode = sqlMode === "validate" ? "default" : "validate";
    if (nextMode === "default") {
      clearAllSqlValidationErrors();
    }
    setSQLMode(nextMode);
  };

  const getModeIcon = (mode: SQLMode) => {
    return mode === "validate" ? (
      <SearchCheck className="h-3 w-3" />
    ) : (
      <DatabaseZap className="h-3 w-3" />
    );
  };

  const getTooltipContent = (mode: SQLMode) => {
    return mode === "validate" ? (
      <div className="text-xs">
        <div className="font-semibold mb-1 flex flex-row items-center gap-1">
          <SearchCheck className="h-3 w-3" />
          Validate Mode
        </div>
        <p>Queries are validated as you write them</p>
      </div>
    ) : (
      <div className="text-xs">
        <div className="font-semibold mb-1 flex flex-row items-center gap-1">
          <DatabaseZap className="h-3 w-3" />
          Default Mode
        </div>
        <p>Standard editing</p>
      </div>
    );
  };

  return (
    <div className="flex flex-row gap-1 items-center">
      <Tooltip delayDuration={300} content={getTooltipContent(sqlMode)}>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleToggleMode}
          className="h-5 px-1.5 text-xs border-border shadow-none hover:bg-accent"
        >
          {getModeIcon(sqlMode)}
          <span className="ml-1">
            {sqlMode === "validate" ? "Validate" : "Default"}
          </span>
        </Button>
      </Tooltip>
    </div>
  );
};

const SQLSelectTrigger: React.FC<SelectTriggerProps> = ({
  children,
  ...props
}) => {
  return (
    <SelectTrigger
      className="text-xs border-border shadow-none! ring-0! h-5 px-1.5 hover:bg-accent transition-colors"
      {...props}
    >
      {children}
    </SelectTrigger>
  );
};
