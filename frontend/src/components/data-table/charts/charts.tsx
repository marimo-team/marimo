/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { XIcon } from "lucide-react";
import type { JSX } from "react";
import React, { Suspense, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CellId } from "@/core/cells/ids";
import type { GetDataUrl } from "@/plugins/impl/DataTablePlugin";
import { uniqueBy } from "@/utils/arrays";
import { reactLazyWithPreload } from "@/utils/lazy";
import { Logger } from "@/utils/Logger";
import { inferFieldTypes } from "../infer-field-types";
import {
  type FieldTypesWithExternalType,
  TOO_MANY_ROWS,
  type TooManyRows,
} from "../types";
import type { ChartPanel } from "./chart-panel";
import { ChartLoadingState } from "./components/chart-states";
import { type ChartSchemaType, getChartDefaults } from "./schemas";
import { getChartTabName, type TabName, tabsStorageAtom } from "./storage";
import type { ChartType } from "./types";

const LazyChartPanel = reactLazyWithPreload<
  React.ComponentProps<typeof ChartPanel>
>(() => import("./chart-panel").then((mod) => ({ default: mod.ChartPanel })));

function preloadChartPanel() {
  void LazyChartPanel.preload().catch((error) => Logger.warn(error));
}

const NEW_CHART_TYPE = "bar" as ChartType;
const DEFAULT_TAB_NAME = "table" as TabName;
const CHART_MAX_ROWS = 50_000;
const CHART_MAX_COLUMNS = 50;

/**
 * Append row-header (index) fields to the chart field list, skipping any whose
 * name already exists as a data column so the chart builder never offers the
 * same axis twice.
 */
export function mergeIndexFields(
  fieldTypes: FieldTypesWithExternalType | null | undefined,
  rowHeaders: FieldTypesWithExternalType | null | undefined,
): FieldTypesWithExternalType {
  const base = fieldTypes ?? [];
  if (!rowHeaders || rowHeaders.length === 0) {
    return base;
  }
  return uniqueBy([...base, ...rowHeaders], (f) => f[0]);
}

export interface TablePanelProps {
  cellId: CellId | null;
  data: unknown[];
  dataTable: JSX.Element;
  totalRows: number | TooManyRows;
  columns: number;
  displayHeader: boolean;
  onCloseChartBuilder?: () => void;
  getDataUrl?: GetDataUrl;
  fieldTypes?: FieldTypesWithExternalType | null;
  rowHeaders?: FieldTypesWithExternalType | null;
}

export const TablePanel: React.FC<TablePanelProps> = ({
  cellId,
  data,
  dataTable,
  totalRows,
  columns,
  getDataUrl,
  fieldTypes,
  rowHeaders,
  displayHeader,
  onCloseChartBuilder,
}) => {
  const [tabsMap, saveTabsMap] = useAtom(tabsStorageAtom);
  const tabs = cellId ? (tabsMap.get(cellId) ?? []) : [];

  const [selectedTab, setSelectedTab] = useState(DEFAULT_TAB_NAME);
  const [tabCounter, setTabCounter] = useState(tabs.length);
  const prevDisplayHeader = useRef(displayHeader);

  // Auto-create a default chart tab when chart builder opens with no tabs
  if (
    displayHeader &&
    !prevDisplayHeader.current &&
    tabs.length === 0 &&
    cellId
  ) {
    prevDisplayHeader.current = displayHeader;
    const tabName = getChartTabName(0, NEW_CHART_TYPE);
    const newTabs = new Map(tabsMap);
    newTabs.set(cellId, [
      { tabName, chartType: NEW_CHART_TYPE, config: getChartDefaults() },
    ]);
    saveTabsMap(newTabs);
    setTabCounter(1);
    setSelectedTab(tabName);
  }
  prevDisplayHeader.current = displayHeader;

  if (!displayHeader || (tabs.length === 0 && !displayHeader)) {
    return dataTable;
  }

  const handleAddTab = () => {
    if (!cellId) {
      return;
    }
    const tabName = getChartTabName(tabCounter, NEW_CHART_TYPE);

    const newTabs = new Map(tabsMap);
    newTabs.set(cellId, [
      ...tabs,
      {
        tabName,
        chartType: NEW_CHART_TYPE,
        config: getChartDefaults(),
      },
    ]);

    saveTabsMap(newTabs);
    setTabCounter(tabCounter + 1);
    setSelectedTab(tabName);
  };

  const handleDeleteTab = (tabName: TabName) => {
    if (!cellId) {
      return;
    }
    const deletedIndex = tabs.findIndex((tab) => tab.tabName === tabName);
    const remaining = tabs.filter((tab) => tab.tabName !== tabName);
    const newTabs = new Map(tabsMap);
    newTabs.set(cellId, remaining);
    saveTabsMap(newTabs);

    if (remaining.length === 0) {
      onCloseChartBuilder?.();
    } else if (tabName === selectedTab) {
      if (deletedIndex < remaining.length) {
        setSelectedTab(remaining[deletedIndex].tabName);
      } else {
        setSelectedTab(remaining[remaining.length - 1].tabName);
      }
    }
  };

  const saveTabChart = ({
    tabName,
    chartType,
    chartConfig,
  }: {
    tabName: TabName;
    chartType: ChartType;
    chartConfig: ChartSchemaType;
  }) => {
    if (!cellId) {
      return;
    }

    const updatedTabs = new Map(tabsMap);
    updatedTabs.set(
      cellId,
      tabs.map((tab) =>
        tab.tabName === tabName
          ? { ...tab, chartType, config: chartConfig }
          : tab,
      ),
    );
    saveTabsMap(updatedTabs);
  };

  const saveTabChartType = (tabName: TabName, chartType: ChartType) => {
    if (!cellId) {
      return;
    }

    const tabs = tabsMap.get(cellId) ?? [];
    const tabIndex = tabs.findIndex((tab) => tab.tabName === tabName);
    if (tabIndex === -1) {
      return;
    }

    const newTabs = tabs.map((tab) =>
      tab.tabName === tabName
        ? {
            ...tab,
            chartType,
            tabName: getChartTabName(tabIndex, chartType),
          }
        : tab,
    );

    const newTabsMap = new Map(tabsMap).set(cellId, newTabs);
    saveTabsMap(newTabsMap);
    setSelectedTab(newTabs[tabIndex].tabName);
  };

  const isLargeDataset =
    totalRows === TOO_MANY_ROWS ||
    totalRows > CHART_MAX_ROWS ||
    columns > CHART_MAX_COLUMNS;

  return (
    <Tabs value={selectedTab} className="-mt-1">
      <TabsList part="table-tabs">
        <TabsTrigger
          className="text-xs"
          value={DEFAULT_TAB_NAME}
          onClick={() => setSelectedTab(DEFAULT_TAB_NAME)}
        >
          Table
        </TabsTrigger>
        {tabs.map((tab, idx) => (
          <TabsTrigger
            key={idx}
            className="text-xs"
            value={tab.tabName}
            onClick={() => setSelectedTab(tab.tabName)}
            onMouseEnter={preloadChartPanel}
            onFocus={preloadChartPanel}
          >
            {tab.tabName}
            <XIcon
              className="w-3 h-3 ml-1 mt-[0.5px] hover:text-red-500 hover:font-semibold"
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteTab(tab.tabName);
              }}
            />
          </TabsTrigger>
        ))}
        <Button
          variant="text"
          size="icon"
          onClick={handleAddTab}
          onMouseEnter={preloadChartPanel}
          onFocus={preloadChartPanel}
          title="Add chart"
        >
          +
        </Button>
      </TabsList>

      <TabsContent className="mt-1 overflow-hidden" value={DEFAULT_TAB_NAME}>
        {dataTable}
      </TabsContent>
      {tabs.map((tab, idx) => {
        const saveChart = (formValues: ChartSchemaType) => {
          saveTabChart({
            tabName: tab.tabName,
            chartType: tab.chartType,
            chartConfig: formValues,
          });
        };
        const saveChartType = (chartType: ChartType) => {
          saveTabChartType(tab.tabName, chartType);
        };
        return (
          <TabsContent key={idx} value={tab.tabName} className="h-[400px] mt-0">
            <Suspense fallback={<ChartLoadingState />}>
              <LazyChartPanel.Component
                tableData={data}
                chartConfig={tab.config}
                chartType={tab.chartType}
                saveChart={saveChart}
                saveChartType={saveChartType}
                getDataUrl={getDataUrl}
                fieldTypes={mergeIndexFields(
                  fieldTypes ?? inferFieldTypes(dataTable.props.data),
                  rowHeaders,
                )}
                isLargeDataset={isLargeDataset}
              />
            </Suspense>
          </TabsContent>
        );
      })}
    </Tabs>
  );
};
