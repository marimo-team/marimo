/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { SQLLanguageAdapter } from "./sql";
import { normalizeName } from "@/core/cells/names";
import { useAutoGrowInputProps } from "@/hooks/useAutoGrowInputProps";
import { getFeatureFlag } from "@/core/config/feature-flag";
import {
  dataSourceConnectionsAtom,
  type DataSourceState,
} from "@/core/cells/data-source-connections";
import { useAtomValue } from "jotai";

export const LanguagePanelComponent: React.FC<{
  view: EditorView;
}> = ({ view }) => {
  const languageAdapter = view.state.field(languageAdapterState);
  const { spanProps, inputProps } = useAutoGrowInputProps({ minWidth: 50 });
  const dataSourceState = useAtomValue(dataSourceConnectionsAtom);

  let actions: React.ReactNode = <div />;
  let showDivider = false;

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
              languageAdapter.dataframeName = e.target.value;
              inputProps.onChange?.(e);
            }}
            onBlur={(e) => {
              // Normalize the name to a valid variable name
              const name = normalizeName(e.target.value, false);
              languageAdapter.dataframeName = name;
              e.target.value = name;

              // Send noop update code event, which will trigger an update to the new output variable name
              view.dispatch({
                changes: {
                  from: 0,
                  to: view.state.doc.length,
                  insert: view.state.doc.toString(),
                },
              });
            }}
            className="min-w-14 w-auto border border-border rounded px-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <span {...spanProps} />
        </label>
        {getFeatureFlag("sql_engines") && (
          <SQLEngineSelect dataSourceState={dataSourceState} />
        )}
        <label className="flex items-center gap-2 ml-auto">
          <input
            type="checkbox"
            onChange={(e) => {
              languageAdapter.showOutput = !e.target.checked;
              // Trigger an update to reflect the change
              view.dispatch({
                changes: {
                  from: 0,
                  to: view.state.doc.length,
                  insert: view.state.doc.toString(),
                },
              });
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

const SQLEngineSelect: React.FC<{ dataSourceState: DataSourceState }> = ({
  dataSourceState,
}) => {
  return (
    <select
      id="sql-engine"
      name="sql-engine"
      className="border border-border rounded px-0.5 focus-visible:outline-none focus-visible:ring-1"
    >
      <option value="In-memory duckdb">In-memory duckdb</option>
      <option value="PostgreSQL">PostgreSQL</option>
      <option value="SQLite">SQLite</option>
    </select>
    // TODO: add a question mark icon that links to how to create an engine
  );
};
