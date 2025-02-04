/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { SQLLanguageAdapter } from "./sql";
import { normalizeName } from "@/core/cells/names";
import { useAutoGrowInputProps } from "@/hooks/useAutoGrowInputProps";
import {
  type ConnectionName,
  dataConnectionsMapAtom,
} from "@/core/datasets/data-source-connections";
import { useAtomValue } from "jotai";
import { AlertCircle, CircleHelpIcon } from "lucide-react";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DatabaseLogo } from "@/components/databases/icon";
import { transformDisplayName } from "@/components/databases/display";
import { useNonce } from "@/hooks/useNonce";

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
        <SQLEngineSelect
          languageAdapter={languageAdapter}
          onChange={triggerUpdate}
        />
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

interface SelectProps {
  languageAdapter: SQLLanguageAdapter;
  onChange: (engine: ConnectionName) => void;
}

const SQLEngineSelect: React.FC<SelectProps> = ({
  languageAdapter,
  onChange,
}) => {
  const connectionsMap = useAtomValue(dataConnectionsMapAtom);

  // Use nonce to force re-render as languageAdapter.engine may not trigger change
  // If it's disconnected, we display the engine variable.
  const selectedEngine = languageAdapter.engine;
  const rerender = useNonce();

  const engineIsDisconnected =
    selectedEngine && !connectionsMap.has(selectedEngine);

  const handleSelectEngine = (value: string) => {
    const nextEngine = connectionsMap.get(value as ConnectionName);
    if (nextEngine) {
      languageAdapter.selectEngine(nextEngine.name);
      rerender();
      onChange(nextEngine.name);
    }
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
            {[...connectionsMap.entries()].map(([key, value]) => (
              <SelectItem key={key} value={value.name}>
                <div className="flex items-center gap-1">
                  <DatabaseLogo className="h-3 w-3" name={value.source} />
                  <span className="truncate">
                    {transformDisplayName(value.display_name)}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
      <TooltipProvider>
        <Tooltip content="How to add a database connection" delayDuration={200}>
          <a
            href="http://docs.marimo.io/guides/working_with_data/sql/#connecting-to-a-custom-database"
            target="_blank"
            rel="noreferrer"
          >
            <CircleHelpIcon
              size={12}
              className="text-[var(--sky-11)] opacity-60 hover:opacity-100"
            />
          </a>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
};
