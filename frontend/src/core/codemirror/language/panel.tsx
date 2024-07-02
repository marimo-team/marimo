/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView, ViewUpdate } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { SQLLanguageAdapter } from "./sql";

export const LanguagePanelComponent: React.FC<{
  view: ViewUpdate | EditorView;
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
