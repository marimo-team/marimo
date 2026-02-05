/* Copyright 2026 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import type { QuotePrefixKind } from "@marimo-team/smart-cells";
import { InfoIcon, PaintRollerIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { normalizeName } from "@/core/cells/names";
import { type ConnectionName, DUCKDB_ENGINE } from "@/core/datasets/engines";
import { useAutoGrowInputProps } from "@/hooks/useAutoGrowInputProps";
import { cellIdState } from "../../cells/state";
import { formatSQL } from "../../format";
import { languageAdapterState } from "../extension";
import { MarkdownLanguageAdapter } from "../languages/markdown";
import {
  SQLLanguageAdapter,
  updateSQLDialectFromConnection,
} from "../languages/sql/sql";
import {
  type LanguageMetadata,
  languageMetadataField,
  updateLanguageMetadata,
} from "../metadata";
import type { LanguageMetadataOf } from "../types";
import { getQuotePrefix, MarkdownQuotePrefixTooltip } from "./markdown";
import { SQLEngineSelect, SQLModeSelect } from "./sql";

const Divider = () => <div className="h-4 border-r border-border" />;

export const LanguagePanelComponent: React.FC<{
  view: EditorView;
}> = ({ view }) => {
  const { spanProps, inputProps } = useAutoGrowInputProps({ minWidth: 50 });
  const languageAdapter = view.state.field(languageAdapterState);
  const cellId = view.state.facet(cellIdState);

  let actions: React.ReactNode = <div />;
  let showDivider = false;

  // Send noop update code event, which will trigger an update to the new output variable name
  const triggerUpdate = <T extends LanguageMetadata>(update: Partial<T>) => {
    view.dispatch({
      effects: updateLanguageMetadata.of(update),
      changes: {
        from: 0,
        to: view.state.doc.length,
        insert: view.state.doc.toString(),
      },
    });
  };

  if (languageAdapter instanceof SQLLanguageAdapter) {
    type Metadata1 = LanguageMetadataOf<SQLLanguageAdapter>;
    const metadata = view.state.field(languageMetadataField) as Metadata1;

    showDivider = true;

    const sanitizeAndTriggerUpdate = (
      e: React.SyntheticEvent<HTMLInputElement>,
    ) => {
      // Normalize the name to a valid variable name
      const name = normalizeName(e.currentTarget.value, false);
      e.currentTarget.value = name;

      triggerUpdate<Metadata1>({
        dataframeName: name,
      });
    };

    const switchEngine = (engine: ConnectionName) => {
      triggerUpdate<Metadata1>({ engine });
      updateSQLDialectFromConnection(view, engine);
    };

    actions = (
      <div className="flex flex-1 gap-2 items-center">
        <label className="flex gap-2 items-center">
          <span className="select-none">Output variable: </span>
          <input
            {...inputProps}
            defaultValue={metadata.dataframeName}
            onChange={(e) => {
              inputProps.onChange?.(e);
            }}
            onBlur={sanitizeAndTriggerUpdate}
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.shiftKey) {
                sanitizeAndTriggerUpdate(e);
              }
            }}
            className="min-w-14 w-auto border border-border rounded px-1 focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
          />
          <span {...spanProps} />
        </label>
        <SQLEngineSelect
          selectedEngine={metadata.engine}
          onChange={switchEngine}
          cellId={cellId}
        />
        <div className="flex items-center gap-2 ml-auto">
          {metadata.engine === DUCKDB_ENGINE && <SQLModeSelect />}
          <Tooltip content="Format SQL">
            <Button
              variant="text"
              size="icon"
              onClick={async () => {
                await formatSQL(view, metadata.engine);
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
                triggerUpdate<Metadata1>({
                  showOutput: !e.target.checked,
                });
              }}
              checked={!metadata.showOutput}
            />
            <span className="select-none">Hide output</span>
          </label>
        </div>
      </div>
    );
  }

  if (languageAdapter instanceof MarkdownLanguageAdapter) {
    showDivider = true;

    type Metadata2 = LanguageMetadataOf<MarkdownLanguageAdapter>;
    const metadata = view.state.field(languageMetadataField) as Metadata2;
    let { quotePrefix } = metadata;

    // Handle the case where the quote prefix is not set
    if (quotePrefix === undefined) {
      quotePrefix = "r";
      triggerUpdate<Metadata2>({ quotePrefix });
    }

    const togglePrefix = (
      prefix: QuotePrefixKind,
      checked: boolean | string,
    ) => {
      if (typeof checked !== "boolean") {
        return;
      }
      const newPrefix = getQuotePrefix({
        currentQuotePrefix: quotePrefix,
        checked,
        prefix,
      });
      triggerUpdate<Metadata2>({
        quotePrefix: newPrefix,
      });
    };

    actions = (
      <div className="flex flex-row w-full justify-end gap-1.5 items-center">
        <div className="flex items-center gap-1.5">
          <span>r</span>
          <Checkbox
            aria-label="Toggle raw string"
            className="w-3 h-3"
            checked={quotePrefix.includes("r")}
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
            checked={quotePrefix.includes("f")}
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
