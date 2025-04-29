/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import { SQLLanguageAdapter } from "./sql";
import { normalizeName } from "@/core/cells/names";
import { useAutoGrowInputProps } from "@/hooks/useAutoGrowInputProps";
import {
  type ConnectionName,
  dataConnectionsMapAtom,
  INTERNAL_SQL_ENGINES,
} from "@/core/datasets/data-source-connections";
import { useAtomValue } from "jotai";
import {
  AlertCircle,
  CircleHelpIcon,
  InfoIcon,
  PaintRollerIcon,
} from "lucide-react";
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
import { DatabaseLogo } from "@/components/databases/icon";
import { transformDisplayName } from "@/components/databases/display";
import { useNonce } from "@/hooks/useNonce";
import type { DataSourceConnection } from "@/core/kernel/messages";
import { formatSQL } from "../format";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { MarkdownLanguageAdapter } from "./markdown";
import type { QuotePrefixKind } from "./utils/quotes";
import { Checkbox } from "@/components/ui/checkbox";

const Divider = () => <div className="h-4 border-r border-border" />;

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
    const sanitizeAndTriggerUpdate = (
      e: React.SyntheticEvent<HTMLInputElement>,
    ) => {
      // Normalize the name to a valid variable name
      const name = normalizeName(e.currentTarget.value, false);
      languageAdapter.setDataframeName(name);
      e.currentTarget.value = name;

      triggerUpdate();
    };
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
            onBlur={sanitizeAndTriggerUpdate}
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.shiftKey) {
                sanitizeAndTriggerUpdate(e);
              }
            }}
            className="min-w-14 w-auto border border-border rounded px-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <span {...spanProps} />
        </label>
        <SQLEngineSelect
          languageAdapter={languageAdapter}
          onChange={triggerUpdate}
        />
        <div className="flex items-center gap-2 ml-auto">
          <Tooltip content="Format SQL">
            <Button
              variant="text"
              size="icon"
              onClick={async () => {
                await formatSQL(view);
              }}
            >
              <PaintRollerIcon className="h-3 w-3" />
            </Button>
          </Tooltip>
          <Divider />
          <label className="flex items-center gap-2">
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
      </div>
    );
  }

  if (languageAdapter instanceof MarkdownLanguageAdapter) {
    showDivider = true;
    const lastQuotePrefix = languageAdapter.lastQuotePrefix;
    const togglePrefix = (
      prefix: QuotePrefixKind,
      checked: boolean | string,
    ) => {
      if (typeof checked !== "boolean") {
        return;
      }
      const newPrefix = getQuotePrefix(lastQuotePrefix, checked, prefix);
      languageAdapter.setQuotePrefix(newPrefix);
      triggerUpdate();
    };

    actions = (
      <div className="flex flex-row w-full justify-end gap-1.5 items-center">
        <div className="flex items-center gap-1.5">
          <span>r</span>
          <Checkbox
            aria-label="Toggle raw string"
            className="w-3 h-3"
            checked={lastQuotePrefix.includes("r")}
            onCheckedChange={(checked) => {
              togglePrefix("r", checked);
            }}
          />
        </div>
        <div className="flex items-center gap-1.5">
          <span>f</span>
          <Checkbox
            aria-label="Toggle f-string"
            className="w-3 h-3"
            checked={lastQuotePrefix.includes("f")}
            onCheckedChange={(checked) => {
              togglePrefix("f", checked);
            }}
          />
        </div>
        <Tooltip content={<MarkdownQuotePrefixTooltip />}>
          <InfoIcon className="w-3 h-3" />
        </Tooltip>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="flex justify-between items-center gap-4 pl-2 pt-2">
        {actions}
        {showDivider && <Divider />}
        {languageAdapter.type}
      </div>
    </TooltipProvider>
  );
};

// Based on the current quote prefix and the checkbox state, return the new quote prefix
export function getQuotePrefix(
  currentQuotePrefix: QuotePrefixKind,
  checked: boolean,
  prefix: QuotePrefixKind,
) {
  let newQuotePrefix = currentQuotePrefix;
  if (checked) {
    // Add a prefix
    if (currentQuotePrefix === "") {
      newQuotePrefix = prefix;
    } else if (currentQuotePrefix !== "rf" && prefix !== currentQuotePrefix) {
      newQuotePrefix = "rf";
    }
  } else {
    // Removing a prefix
    if (currentQuotePrefix === prefix) {
      // Removing the only prefix
      newQuotePrefix = "";
    } else if (currentQuotePrefix === "rf") {
      newQuotePrefix = prefix === "r" ? "f" : "r";
    }
  }

  return newQuotePrefix;
}

const MarkdownQuotePrefixTooltip: React.FC = () => {
  return (
    <div className="flex flex-col gap-3.5">
      <section className="flex flex-col gap-0.5">
        <header className="flex items-center gap-1">
          <code className="text-xs px-1 py-0.5 bg-[var(--slate-2)] rounded">
            r
          </code>
          <span className="font-semibold">Raw String</span>
        </header>
        <p className="text-sm text-muted-foreground">
          Write LaTeX without escaping special characters
        </p>
        <pre className="text-xs bg-[var(--slate-2)] p-2 rounded">
          \alpha \beta
        </pre>
      </section>

      <section className="flex flex-col gap-0.5">
        <header className="flex items-center gap-1">
          <code className="text-xs px-1 py-0.5 bg-[var(--slate-2)] rounded">
            f
          </code>
          <span className="font-semibold">Format String</span>
        </header>
        <p className="text-sm text-muted-foreground">
          Interpolate Python values
        </p>
        <pre className="text-xs bg-[var(--slate-2)] p-2 rounded">
          Hello {"{name}"}! 😁
        </pre>
      </section>
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

  const internalEngineConnections: DataSourceConnection[] = [];
  const userDefinedConnections: DataSourceConnection[] = [];
  for (const [connName, connection] of connectionsMap.entries()) {
    INTERNAL_SQL_ENGINES.has(connName)
      ? internalEngineConnections.push(connection)
      : userDefinedConnections.push(connection);
  }

  // Use nonce to force re-render as languageAdapter.engine may not trigger change
  // If it's disconnected, we display the engine variable.
  const selectedEngine = languageAdapter.engine;
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
      languageAdapter.selectEngine(nextEngine.name);
      rerender();
      onChange(nextEngine.name);
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
