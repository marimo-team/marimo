/* Copyright 2024 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import {
  BarChartIcon,
  DatabaseIcon,
  HashIcon,
  SlidersHorizontalIcon,
  SparklesIcon,
  TableIcon,
  TrendingUpIcon,
  TypeIcon,
} from "lucide-react";
import React, { memo } from "react";
import useEvent from "react-use-event-hook";
import { MarkdownIcon, PythonIcon } from "@/components/editor/cell/code/icons";
import { useDataFrameColumns } from "@/components/editor/cell/useDataFrameColumns";
import { useDataFrameVariables } from "@/components/editor/cell/useDataFrameVariables";
import { useRunCells } from "@/components/editor/cell/useRunCells";
import { useUniqueVariableName } from "@/components/editor/cell/useUniqueVariableName";
import { AddDatabaseDialogContent } from "@/components/editor/database/add-database-form";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu";
import {
  maybeAddAltairImport,
  maybeAddMarimoImport,
} from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { LanguageAdapters } from "@/core/codemirror/language/LanguageAdapters";
import { canvasAIPromptAtom } from "../state";

interface AddCellMenuItemsProps {
  direction: "above" | "below" | "left" | "right";
  cellId: CellId | null;
  nodePosition?: { x: number; y: number };
  nodeSize?: { width: number; height: number };
}

// Constants
const AGGREGATION_TYPES: Array<{
  type: "min" | "max" | "mean" | "sum" | "count";
  label: string;
}> = [
  { type: "min", label: "Min" },
  { type: "max", label: "Max" },
  { type: "mean", label: "Mean" },
  { type: "sum", label: "Sum" },
  { type: "count", label: "Count" },
] as const;

// Utility functions
const renderIcon = (icon: React.ReactNode) => {
  return <div className="mr-3 text-muted-foreground">{icon}</div>;
};

const generateChartCode = (
  variableName: string,
  columnName: string,
  columnType?: string,
): string => {
  // Generate chart based on column type
  switch (columnType) {
    case "number":
    case "integer":
      // Histogram for numeric columns
      return `_chart = alt.Chart(${variableName}).mark_bar().encode(
    x=alt.X("${columnName}:Q", bin=True),
    y="count()"
)
_chart`;

    case "string":
      // Bar chart for categorical columns
      return `_chart = (
    alt.Chart(${variableName})
    .mark_bar()
    .transform_aggregate(count="count()", groupby=["${columnName}"])
    .transform_window(
        rank="rank()",
        sort=[alt.SortField("count", order="descending")]
    )
    .transform_filter(alt.datum.rank <= 10)
    .encode(
        y=alt.Y("${columnName}:N", sort="-x"),
        x="count:Q"
    )
)
_chart`;

    case "boolean":
      // Pie chart for boolean columns
      return `_chart = (
    alt.Chart(${variableName})
    .mark_arc()
    .encode(
        theta="count()",
        color="${columnName}:N"
    )
)
_chart`;

    case "date":
    case "datetime":
    case "time":
      // Area chart for temporal columns
      return `_chart = alt.Chart(${variableName}).mark_area().encode(
    x="${columnName}:T",
    y="count()"
)
_chart`;

    default:
      // Default bar chart
      return `_chart = alt.Chart(${variableName}).mark_bar().encode(
    x="${columnName}:N",
    y="count()"
)
_chart`;
  }
};

/**
 * Reusable menu items component for add cell buttons
 * Self-contained with its own hooks and logic for better composition
 */
const AddCellMenuItemsComponent: React.FC<AddCellMenuItemsProps> = ({
  direction,
  cellId,
  nodePosition,
  nodeSize,
}) => {
  // biome-ignore lint/suspicious/noConsole: For debugging
  console.count("AddCellMenuItems rendered");
  // Hooks
  const { createNewCell } = useCellActions();
  const getUniqueVariableName = useUniqueVariableName();
  const dataframeVariables = useDataFrameVariables();
  const dataframeColumns = useDataFrameColumns();
  const runCells = useRunCells();
  const setAIPromptState = useSetAtom(canvasAIPromptAtom);
  const { openModal, closeModal } = useImperativeModal();

  // Handlers
  const handleAddCell = useEvent(
    (
      dir: "above" | "below" | "left" | "right",
      opts: { code: string; hideCode?: boolean },
    ) => {
      // Generate a new cell ID so we can run it after creation
      const newCellId = CellId.create();

      // If cellId is null, add at the end of the notebook
      if (cellId === null) {
        createNewCell({
          cellId: "__end__" as CellId,
          before: false,
          code: opts.code,
          hideCode: opts.hideCode,
          newCellId,
        });
      } else {
        createNewCell({
          cellId,
          before: dir === "above" || dir === "left",
          code: opts.code,
          hideCode: opts.hideCode,
          newCellId,
        });
      }

      // Store the position info for the canvas to use when adding the new cell
      if (nodePosition !== undefined) {
        const meta = {
          direction: dir,
          referencePosition: nodePosition,
          referenceSize: nodeSize ?? { width: 0, height: 0 },
        };
        // Store in session storage temporarily so canvas can pick it up
        sessionStorage.setItem("newCellPositionMeta", JSON.stringify(meta));
      }

      // Automatically run the newly created cell
      // Use a short timeout to ensure the cell is fully created before running
      setTimeout(() => {
        runCells([newCellId]);
      }, 0);
    },
  );

  const handleOpenAIPrompt = useEvent(() => {
    setAIPromptState({ isOpen: true, prompt: "" });
  });

  const handleOpenDatasources = useEvent(() => {
    openModal(<AddDatabaseDialogContent onClose={closeModal} />);
  });

  const createPythonCell = useEvent(() => {
    handleAddCell(direction, { code: "" });
  });

  const createMarkdownCell = useEvent(() => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    handleAddCell(direction, {
      code: LanguageAdapters.markdown.defaultCode,
      hideCode: true,
    });
  });

  const createSQLCell = useEvent(() => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    handleAddCell(direction, { code: LanguageAdapters.sql.defaultCode });
  });

  const createUISliderCell = useEvent(() => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    const varName = getUniqueVariableName("slider");
    const code = `${varName} = mo.ui.slider(0, 10)\n${varName}`;
    handleAddCell(direction, { code });
  });

  const createUITextCell = useEvent(() => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    const varName = getUniqueVariableName("text");
    const code = `${varName} = mo.ui.text()\n${varName}`;
    handleAddCell(direction, { code });
  });

  const createUINumberCell = useEvent(() => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    const varName = getUniqueVariableName("number");
    const code = `${varName} = mo.ui.number()\n${varName}`;
    handleAddCell(direction, { code });
  });

  const createUITextAreaCell = useEvent(() => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    const varName = getUniqueVariableName("text_area");
    const code = `${varName} = mo.ui.text_area()\n${varName}`;
    handleAddCell(direction, { code });
  });

  const createTableCell = useEvent((variableName: string) => {
    maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
    const code = `mo.ui.table(${variableName})`;
    handleAddCell(direction, { code });
  });

  const createAggregationCell = useEvent(
    (
      variableName: string,
      columnName: string,
      aggregationType: "min" | "max" | "mean" | "sum" | "count",
    ) => {
      maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
      const code = `mo.stat(label="${columnName}", caption="${aggregationType.toUpperCase()}", value=${variableName}["${columnName}"].${aggregationType}())`;
      handleAddCell(direction, { code });
    },
  );

  const createChartCell = useEvent(
    (variableName: string, columnName: string, columnType?: string) => {
      maybeAddMarimoImport({ autoInstantiate: true, createNewCell });
      maybeAddAltairImport({ autoInstantiate: true, createNewCell });
      const code = generateChartCode(variableName, columnName, columnType);
      handleAddCell(direction, { code });
    },
  );

  const renderAggregationSubmenu = () => {
    if (dataframeColumns.length === 0) {
      return null;
    }

    return (
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          {renderIcon(<TrendingUpIcon size={13} strokeWidth={1.5} />)}
          Aggregation
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="max-h-[300px] overflow-auto">
          {dataframeColumns.map((df) => (
            <DropdownMenuSub key={df.name}>
              <DropdownMenuSubTrigger>
                <div className="flex flex-col items-start">
                  <span className="font-medium">{df.name}</span>
                  {df.value && (
                    <span className="text-xs text-muted-foreground">
                      {df.value}
                    </span>
                  )}
                </div>
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="max-h-[300px] overflow-auto">
                {df.columns.length === 0 ? (
                  <div className="px-2 py-1 text-xs text-muted-foreground">
                    No columns available
                  </div>
                ) : (
                  df.columns.map((column) => (
                    <DropdownMenuSub key={column.name}>
                      <DropdownMenuSubTrigger>
                        <div className="flex flex-col items-start">
                          <span className="font-medium">{column.name}</span>
                          {column.type && (
                            <span className="text-xs text-muted-foreground">
                              {column.type}
                            </span>
                          )}
                        </div>
                      </DropdownMenuSubTrigger>
                      <DropdownMenuSubContent className="max-h-[300px] overflow-auto">
                        {AGGREGATION_TYPES.map((agg) => (
                          <DropdownMenuItem
                            key={agg.type}
                            onClick={() =>
                              createAggregationCell(
                                df.name,
                                column.name,
                                agg.type,
                              )
                            }
                          >
                            {agg.label}
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                  ))
                )}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    );
  };

  const renderChartSubmenu = () => {
    if (dataframeColumns.length === 0) {
      return null;
    }

    return (
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          {renderIcon(<BarChartIcon size={13} strokeWidth={1.5} />)}
          Chart
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="max-h-[300px] overflow-auto">
          {dataframeColumns.map((df) => (
            <DropdownMenuSub key={df.name}>
              <DropdownMenuSubTrigger>
                <div className="flex flex-col items-start">
                  <span className="font-medium">{df.name}</span>
                  {df.value && (
                    <span className="text-xs text-muted-foreground">
                      {df.value}
                    </span>
                  )}
                </div>
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="max-h-[300px] overflow-auto">
                {df.columns.length === 0 ? (
                  <div className="px-2 py-1 text-xs text-muted-foreground">
                    No columns available
                  </div>
                ) : (
                  df.columns.map((column) => (
                    <DropdownMenuItem
                      key={column.name}
                      onClick={() =>
                        createChartCell(df.name, column.name, column.type)
                      }
                    >
                      <div className="flex flex-col items-start">
                        <span className="font-medium">{column.name}</span>
                        {column.type && (
                          <span className="text-xs text-muted-foreground">
                            {column.type}
                          </span>
                        )}
                      </div>
                    </DropdownMenuItem>
                  ))
                )}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    );
  };

  const renderTableSubmenu = () => {
    if (dataframeVariables.length === 0) {
      return null;
    }

    return (
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          {renderIcon(<TableIcon size={13} strokeWidth={1.5} />)}
          Table
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="max-h-[300px] overflow-auto">
          {dataframeVariables.map((df) => (
            <DropdownMenuItem
              key={df.name}
              onClick={() => createTableCell(df.name)}
            >
              <div className="flex flex-col items-start">
                <span className="font-medium">{df.name}</span>
                {df.value && (
                  <span className="text-xs text-muted-foreground">
                    {df.value}
                  </span>
                )}
              </div>
            </DropdownMenuItem>
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    );
  };

  return (
    <>
      <div className="flex flex-col gap-2 text-xs text-muted-foreground px-2 py-1">
        Add a new cell
      </div>
      <DropdownMenuItem onClick={handleOpenAIPrompt}>
        {renderIcon(<SparklesIcon size={13} strokeWidth={1.5} />)}
        Generate with AI
      </DropdownMenuItem>
      <DropdownMenuItem onClick={handleOpenDatasources}>
        {renderIcon(<DatabaseIcon size={13} strokeWidth={1.5} />)}
        Data sources
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem onClick={createPythonCell}>
        {renderIcon(<PythonIcon />)}
        Python cell
      </DropdownMenuItem>
      <DropdownMenuItem onClick={createMarkdownCell}>
        {renderIcon(<MarkdownIcon />)}
        Markdown cell
      </DropdownMenuItem>
      <DropdownMenuItem onClick={createSQLCell}>
        {renderIcon(<DatabaseIcon size={13} strokeWidth={1.5} />)}
        SQL cell
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem onClick={createUISliderCell}>
        {renderIcon(<SlidersHorizontalIcon size={13} strokeWidth={1.5} />)}
        Slider input
      </DropdownMenuItem>
      <DropdownMenuItem onClick={createUITextCell}>
        {renderIcon(<TypeIcon size={13} strokeWidth={1.5} />)}
        Text input
      </DropdownMenuItem>
      <DropdownMenuItem onClick={createUINumberCell}>
        {renderIcon(<HashIcon size={13} strokeWidth={1.5} />)}
        Number input
      </DropdownMenuItem>
      <DropdownMenuItem onClick={createUITextAreaCell}>
        {renderIcon(<TypeIcon size={13} strokeWidth={1.5} />)}
        Text area
      </DropdownMenuItem>
      {renderTableSubmenu()}
      {renderAggregationSubmenu()}
      {renderChartSubmenu()}
    </>
  );
};

export const AddCellMenuItems = memo(AddCellMenuItemsComponent);
AddCellMenuItems.displayName = "AddCellMenuItems";
