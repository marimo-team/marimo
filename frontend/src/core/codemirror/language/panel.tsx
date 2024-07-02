/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { SQLLanguageAdapter } from "./sql";
import { normalizeName } from "@/core/cells/names";

export const LanguagePanelComponent: React.FC<{
  view: EditorView;
}> = ({ view }) => {
  const languageAdapter = view.state.field(languageAdapterState);
  let actions: React.ReactNode = <div />;

  if (languageAdapter instanceof SQLLanguageAdapter) {
    actions = (
      <div className="flex gap-2">
        Output variable:{" "}
        <input
          defaultValue={languageAdapter.dataframeName}
          onChange={(e) => (languageAdapter.dataframeName = e.target.value)}
          onBlur={(e) => {
            // Normalize the name to a valid variable name
            const name = normalizeName(e.target.value);
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
          className="w-20 border border-border rounded px-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </div>
    );
  }

  return (
    <div className="flex justify-between px-2 pt-2">
      {actions}
      {languageAdapter.type}
    </div>
  );
};
