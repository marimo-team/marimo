/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { DEFAULT_ENGINE, SQLLanguageAdapter } from "./sql";
import { normalizeName } from "@/core/cells/names";
import { useAutoGrowInputProps } from "@/hooks/useAutoGrowInputProps";
import { getFeatureFlag } from "@/core/config/feature-flag";
import {
  type ConnectionName,
  dataConnectionsMapAtom,
} from "@/core/cells/data-source-connections";
import { useAtomValue } from "jotai";
import { CircleHelpIcon } from "lucide-react";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { useState } from "react";

export const LanguagePanelComponent: React.FC<{
  view: EditorView;
}> = ({ view }) => {
  const languageAdapter = view.state.field(languageAdapterState);
  const { spanProps, inputProps } = useAutoGrowInputProps({ minWidth: 50 });

  let actions: React.ReactNode = <div />;
  let showDivider = false;

  // Send noop update code event, which will trigger an update to the new output variable name
  const triggerUpdate = () => {
    view.dispatch({
      changes: {
        from: 0,
        to: view.state.doc.length,
        insert: view.state.doc.toString(),
      },
    });
  };

  if (languageAdapter instanceof SQLLanguageAdapter) {
    showDivider = true;
    actions = (
      <div className="flex flex-1 gap-2 relative items-center">
        <label className="flex gap-2 items-center">
          <span className="select-none">Output variable: </span>
          <input
            {...inputProps}
            defaultValue={languageAdapter.dataframeName}
            onChange={(e) => {
              languageAdapter.setDataframeName(e.target.value);
              inputProps.onChange?.(e);
            }}
            onBlur={(e) => {
              // Normalize the name to a valid variable name
              const name = normalizeName(e.target.value, false);
              languageAdapter.setDataframeName(name);
              e.target.value = name;

              triggerUpdate();
            }}
            className="min-w-14 w-auto border border-border rounded px-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <span {...spanProps} />
        </label>
        {getFeatureFlag("sql_engines") && (
          <SQLEngineSelect
            languageAdapter={languageAdapter}
            onChange={triggerUpdate}
          />
        )}
        <label className="flex items-center gap-2 ml-auto">
          <input
            type="checkbox"
            onChange={(e) => {
              languageAdapter.setShowOutput(!e.target.checked);
              triggerUpdate();
            }}
            checked={!languageAdapter.showOutput}
          />
          <span className="select-none">Hide output</span>
        </label>
      </div>
    );
  }

  return (
    <div className="flex justify-between items-center gap-4 pl-2 pt-2">
      {actions}
      {showDivider && <div className="h-4 border-r border-border" />}
      {languageAdapter.type}
    </div>
  );
};

const SQLEngineSelect: React.FC<{
  languageAdapter: SQLLanguageAdapter;
  onChange: (engine: ConnectionName) => void;
}> = ({ languageAdapter, onChange }) => {
  // use local state as languageAdapter may not trigger an update
  const [selectedEngine, setSelectedEngine] = useState(languageAdapter.engine);
  const connectionsMap = useAtomValue(dataConnectionsMapAtom);

  return (
    <div className="flex flex-row gap-1 items-center">
      <select
        id="sql-engine"
        name="sql-engine"
        className="border border-border rounded px-0.5 focus-visible:outline-none focus-visible:ring-1"
        value={selectedEngine}
        onChange={(e) => {
          const nextEngine = e.target.value as ConnectionName;
          languageAdapter.selectEngine(nextEngine);
          setSelectedEngine(nextEngine);
          onChange(nextEngine);
        }}
      >
        {/* Fallback option if an existing option is deleted, 
        let's users intentionally switch to default if needed */}
        <option value={DEFAULT_ENGINE}>Choose an option</option>
        {[...connectionsMap.entries()].map(([key, value]) => (
          <option key={key} value={value.name}>
            {value.display_name}
          </option>
        ))}
      </select>
      <TooltipProvider>
        <Tooltip
          content="Find out how to add an SQL engine"
          delayDuration={200}
        >
          <a href="https://TODO.com" target="_blank" rel="noreferrer">
            <CircleHelpIcon
              size={13}
              className="text-[var(--sky-11)] opacity-60 hover:opacity-100"
            />
          </a>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};
