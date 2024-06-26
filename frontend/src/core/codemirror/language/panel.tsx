/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView, ViewUpdate } from "@codemirror/view";
import { languageAdapterState } from "./extension";

export const LanguagePanelComponent: React.FC<{view: ViewUpdate | EditorView}> = ({view}) => {
  const type = view.state.field(languageAdapterState).type;
  let actions: React.ReactNode = <div/>
  if (type === 'sql') {
    actions = (
      <div className="flex gap-2">
        Output variable: <input className="w-20 border border-border rounded px-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring" />
      </div>
    );
  }

  return (
    <div className="flex justify-between px-2 pt-2">
      {actions}
      {type}
    </div>
  );
}
