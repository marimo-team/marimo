/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { SQLLanguageAdapter } from "./sql";
import { normalizeName } from "@/core/cells/names";
import { useAutoGrowInputProps } from "@/hooks/useAutoGrowInputProps";

export const LanguagePanelComponent: React.FC<{
  view: EditorView;
}> = ({ view }) => {
  const languageAdapter = view.state.field(languageAdapterState);
  const { spanProps, inputProps } = useAutoGrowInputProps({ minWidth: 50 });
  let actions: React.ReactNode = <div />;
  let showDivider = false;

  if (languageAdapter instanceof SQLLanguageAdapter) {
    showDivider = true;
    actions = (
      <div className="flex flex-1 gap-2 relative items-center justify-between">
        <div className="flex gap-2 items-center">
          <label htmlFor="dataframeName" className="select-none">
            Output variable:{" "}
          </label>
          <input
            id="dataframeName"
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
        </div>
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="hideOutput"
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
          <label className="select-none" htmlFor="hideOutput">
            Hide output
          </label>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-between items-center gap-4 px-2 pt-2">
      {actions}
      {showDivider && <div className="h-4 border-r border-border" />}
      {languageAdapter.type}
    </div>
  );
};
